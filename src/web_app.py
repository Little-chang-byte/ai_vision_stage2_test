import hashlib
import hmac
import json
import os
import secrets
import re
import time
import io
from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.responses import FileResponse
import uuid
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import DateTime, Integer, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

try:
    from .traditional_pipeline import YoloDetector, validate_yolo_result
    from .vlm_pipeline import run_vlm
except ImportError:
    from traditional_pipeline import YoloDetector, validate_yolo_result
    from vlm_pipeline import run_vlm
try:
    from .comparison import compare_row
    from .vlm_pipeline import validate_result_record
except ImportError:
    from comparison import compare_row
    from vlm_pipeline import validate_result_record

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(ROOT / "data" / "uploads")))
RESULT_DIR = Path(os.getenv("RESULT_DIR", str(ROOT / "results" / "web")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'stage3.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "")
DEMO_USER = os.getenv("DEMO_USER", "teacher")
DEMO_PASSWORD_HASH = os.getenv("DEMO_PASSWORD_HASH", "")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    image_path: Mapped[str] = mapped_column(Text)
    image_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    yolo_status: Mapped[str] = mapped_column(String(32), default="pending")
    vlm_status: Mapped[str] = mapped_column(String(32), default="pending")
    yolo_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    vlm_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    comparison_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)
if "comparison_result" not in {column["name"] for column in inspect(engine).get_columns("tasks")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN comparison_result TEXT"))
if "note" not in {column["name"] for column in inspect(engine).get_columns("tasks")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN note TEXT NOT NULL DEFAULT ''"))
app = FastAPI(title="AI 双方案视觉对比", version="3.0.0")
bearer = HTTPBearer(auto_error=False)


def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "需要登录")
    try:
        if not JWT_SECRET:
            raise HTTPException(503, "JWT_SECRET 未配置")
        claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        if not claims.get("sub") or claims["sub"] != DEMO_USER: raise HTTPException(401, "Token 用户无效")
        return claims
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Token 无效或已过期") from exc


MODEL_LOCK = threading.Lock()


def run_task(task_id: str):
    with MODEL_LOCK:
        _run_task(task_id)


def _run_task(task_id: str):
    # Compare-and-set prevents broker redelivery from executing models twice.
    from sqlalchemy import update
    with SessionLocal() as db:
        claimed = db.execute(update(Task).where(Task.id == task_id, Task.status == "pending").values(status="running"))
        db.commit()
        if claimed.rowcount != 1:
            return
        task = db.get(Task, task_id)
        errors = []
        for model_name, runner, validator in [
            ("yolo", lambda: YoloDetector().detect(task.image_path, task_id, str(RESULT_DIR)), validate_yolo_result),
            ("vlm", lambda: run_vlm(task.image_path, task_id, str(RESULT_DIR / "vlm")), validate_result_record),
        ]:
            setattr(task, model_name + "_status", "running")
            db.commit()
            started = time.perf_counter()
            try:
                if hashlib.sha256(Path(task.image_path).read_bytes()).hexdigest() != task.image_sha256:
                    raise ValueError("INPUT_HASH_CHANGED")
                raw = runner()
                setattr(task, model_name + "_result", json.dumps(raw, ensure_ascii=False))
                validator(raw)
                setattr(task, model_name + "_status", "success")
            except Exception as exc:
                setattr(task, model_name + "_status", "failed")
                errors.append(f"{model_name}: {exc}")
                saved_raw = getattr(task, model_name + "_result")
                if saved_raw and isinstance(json.loads(saved_raw), dict) and json.loads(saved_raw).get("error"):
                    errors.append(str(json.loads(saved_raw)["error"]))
                if getattr(task, model_name + "_result") is None:
                    setattr(task, model_name + "_result", json.dumps({"error": str(exc), "runtime_seconds": round(time.perf_counter() - started, 4)}))
            db.commit()
        yolo = json.loads(task.yolo_result)
        vlm = json.loads(task.vlm_result)
        # Include only validated counts in partial comparisons.
        comparison = {
            "image_id": task.id,
            "yolo_status": task.yolo_status,
            "vlm_status": task.vlm_status,
            "yolo_counts": yolo.get("counts", {}) if task.yolo_status == "success" else {},
            "vlm_counts": vlm.get("counts", {}) if task.vlm_status == "success" else {},
            "yolo_runtime_seconds": yolo.get("runtime_seconds"),
            "vlm_runtime_seconds": vlm.get("runtime_seconds"),
        }
        if task.yolo_status == task.vlm_status == "success":
            comparison.update(compare_row(task.id, yolo, vlm))
        task.comparison_result = json.dumps(comparison, ensure_ascii=False)
        task.error = " | ".join(errors) or None
        successes = sum(status == "success" for status in [task.yolo_status, task.vlm_status])
        task.status = ["failed", "partial_success", "success"][successes]
        db.commit()


@app.get("/health")
def health():
    return {"status": "ok", "task_mode": os.getenv("TASK_MODE", "celery"), "models": {"yolo": "available", "vlm": os.getenv("VLM_MODEL", "qwen3-vl:4b")}}


@app.post("/api/auth/login")
def login(payload: dict):
    if not JWT_SECRET or not DEMO_PASSWORD_HASH:
        raise HTTPException(503, "JWT_SECRET 和 DEMO_PASSWORD_HASH 必须配置")
    if not secrets.compare_digest(str(payload.get("username", "")), DEMO_USER) or not verify_password(str(payload.get("password", "")), DEMO_PASSWORD_HASH):
        raise HTTPException(401, "用户名或密码错误")
    token = jwt.encode({"sub": DEMO_USER, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), _: dict = Depends(auth)):
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(415, "仅支持 JPG、PNG、WEBP")
    data = await file.read(10 * 1024 * 1024 + 1)
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "图片为空或超过 10MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported image")
            suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image.format]
            image.verify()
    except (UnidentifiedImageError, ValueError, OSError) as exc:
        raise HTTPException(415, "图片不能解码") from exc
    sha = hashlib.sha256(data).hexdigest()
    path = UPLOAD_DIR / f"{sha}{suffix}"
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise HTTPException(409, "上传目标已存在且内容不一致")
    else:
        with path.open("xb") as handle:
            handle.write(data)
    return {"image_path": str(path), "image_sha256": sha, "filename": file.filename}


@app.post("/api/compare")
def compare(payload: dict, tasks: BackgroundTasks, _: dict = Depends(auth)):
    path = Path(str(payload.get("image_path", ""))).resolve()
    if not path.is_file() or UPLOAD_DIR.resolve() not in path.parents:
        raise HTTPException(400, "请先上传有效图片")
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    claimed_sha = payload.get("image_sha256", "")
    if not isinstance(claimed_sha, str) or not re.fullmatch("[0-9a-f]{64}", claimed_sha):
        raise HTTPException(400, "需要合法 image_sha256")
    if path.stem != actual_sha or not claimed_sha or not hmac.compare_digest(claimed_sha, actual_sha):
        raise HTTPException(400, "图片哈希校验失败")
    task_id = str(uuid.uuid4())
    task = Task(id=task_id, image_path=str(path), image_sha256=actual_sha)
    with SessionLocal() as db:
        db.add(task)
        db.commit()
    if os.getenv("TASK_MODE", "celery") == "local":
        tasks.add_task(run_task, task_id)
        return {"task_id": task_id, "status": "pending", "image_sha256": task.image_sha256}
    try:
        from .queue_app import execute_task
        execute_task.apply_async(args=[task_id], task_id=task_id, retry=False)
    except Exception as exc:
        with SessionLocal() as db:
            failed = db.get(Task, task_id)
            failed.status = "failed"
            failed.error = "QUEUE_UNAVAILABLE: " + type(exc).__name__
            db.commit()
        raise HTTPException(503, {"task_id": task_id, "error": "任务队列不可用，请启动 Redis 和 worker"}) from exc
    return {"task_id": task_id, "status": "pending", "image_sha256": task.image_sha256}


def task_view(task: Task):
    import json
    return {"task_id": task.id, "status": task.status, "image_sha256": task.image_sha256, "yolo_status": task.yolo_status, "vlm_status": task.vlm_status, "yolo": json.loads(task.yolo_result) if task.yolo_result else None, "vlm": json.loads(task.vlm_result) if task.vlm_result else None, "comparison": json.loads(task.comparison_result) if task.comparison_result else None, "error": task.error, "note": task.note, "created_at": task.created_at.isoformat()}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256" or not 100000 <= int(iterations) <= 1000000:
            return False
        salt = bytes.fromhex(salt_hex)
        digest = bytes.fromhex(digest_hex)
        if len(salt) != 16 or len(digest) != 32:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, digest)
    except (AttributeError, ValueError, TypeError):
        return False


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, _: dict = Depends(auth)):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        return task_view(task)


@app.get("/api/history")
def history(_: dict = Depends(auth)):
    with SessionLocal() as db:
        return [task_view(task) for task in db.scalars(select(Task).order_by(Task.created_at.desc()).limit(50))]


class TaskNote(BaseModel):
    note: str


@app.patch("/api/tasks/{task_id}")
def update_note(task_id: str, payload: TaskNote, _: dict = Depends(auth)):
    if len(payload.note) > 2000:
        raise HTTPException(400, "备注过长")
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        task.note = payload.note
        db.commit()
        return task_view(task)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, confirm: bool = False, _: dict = Depends(auth)):
    if not confirm:
        raise HTTPException(400, "需要 confirm=true 确认删除")
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        if task.status in {"pending", "running"}:
            raise HTTPException(409, "执行中的任务不能删除")
        db.delete(task)
        db.commit()
    return {"deleted": task_id}


@app.get("/api/tasks/{task_id}/image/{kind}")
def task_image(task_id: str, kind: str, _: dict = Depends(auth)):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(404, "任务不存在")
        if kind == "original":
            path, root = Path(task.image_path), UPLOAD_DIR
        elif kind == "yolo":
            path, root = RESULT_DIR / f"{task.id}.jpg", RESULT_DIR
        else:
            raise HTTPException(404, "图片类型不存在")
        if path.is_symlink() or root.resolve() not in path.resolve().parents or not path.is_file():
            raise HTTPException(404, "图片不存在")
        return FileResponse(path, headers={"Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((ROOT / "frontend" / "index.html").read_text(encoding="utf-8"))
