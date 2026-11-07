import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
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
UPLOAD_DIR = ROOT / "data" / "uploads"
RESULT_DIR = ROOT / "results" / "web"
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)
if "comparison_result" not in {column["name"] for column in inspect(engine).get_columns("tasks")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE tasks ADD COLUMN comparison_result TEXT"))
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


def run_task(task_id: str):
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task:
            return
        task.status = "running"
        db.commit()
        try:
            yolo = YoloDetector().detect(task.image_path, task_id, str(RESULT_DIR))
            task.yolo_result = json.dumps(yolo, ensure_ascii=False)
            validate_yolo_result(yolo)
            task.yolo_status = "success"
        except Exception as exc:
            task.yolo_status, task.error = "failed", f"YOLO: {exc}"
        db.commit()
        try:
            vlm = run_vlm(task.image_path, task_id, str(RESULT_DIR / "vlm"))
            task.vlm_result = json.dumps(vlm, ensure_ascii=False)
            try:
                validate_result_record(vlm)
                task.vlm_status = "success"
            except ValueError as exc:
                task.vlm_status = "failed"
                task.error = (task.error + " | " if task.error else "") + f"VLM validation: {exc}"
            if vlm.get("error"):
                task.error = (task.error + " | " if task.error else "") + f"VLM: {vlm['error']}"
        except Exception as exc:
            task.vlm_status, task.error = "failed", (task.error + " | " if task.error else "") + f"VLM: {exc}"
        if task.yolo_status == "success" and task.vlm_status == "success":
            task.comparison_result = json.dumps(compare_row(task.id, json.loads(task.yolo_result), json.loads(task.vlm_result)), ensure_ascii=False)
        task.status = "success" if task.yolo_status == task.vlm_status == "success" else "partial_success" if "success" in {task.yolo_status, task.vlm_status} else "failed"
        db.commit()


@app.get("/health")
def health():
    return {"status": "ok", "models": {"yolo": "available", "vlm": os.getenv("VLM_MODEL", "qwen3-vl:4b")}}


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
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "图片为空或超过 10MB")
    suffix = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
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
    claimed_sha = str(payload.get("image_sha256", ""))
    if not claimed_sha or not hmac.compare_digest(claimed_sha, actual_sha):
        raise HTTPException(400, "图片哈希校验失败")
    task_id = str(uuid.uuid4())
    task = Task(id=task_id, image_path=str(path), image_sha256=actual_sha)
    with SessionLocal() as db:
        db.add(task)
        db.commit()
    tasks.add_task(run_task, task_id)
    return {"task_id": task_id, "status": "pending", "image_sha256": task.image_sha256}


def task_view(task: Task):
    import json
    return {"task_id": task.id, "status": task.status, "image_sha256": task.image_sha256, "yolo_status": task.yolo_status, "vlm_status": task.vlm_status, "yolo": json.loads(task.yolo_result) if task.yolo_result else None, "vlm": json.loads(task.vlm_result) if task.vlm_result else None, "comparison": json.loads(task.comparison_result) if task.comparison_result else None, "error": task.error, "created_at": task.created_at.isoformat()}


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
    except (ValueError, TypeError):
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


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>AI 双方案视觉对比</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px}button{padding:10px 18px;margin:8px}section{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{white-space:pre-wrap;background:#f4f4f4;padding:14px;min-height:160px}img{max-width:100%;max-height:360px}</style><h1>AI 双方案视觉对比</h1><p>同一张图片分别调用真实 YOLO 与 Ollama 多模态模型。</p><input id='file' type='file' accept='image/jpeg,image/png,image/webp'><button onclick='run()'>开始真实对比</button><p id='state'></p><img id='preview'><section><div><h2>YOLO</h2><pre id='yolo'></pre></div><div><h2>多模态模型</h2><pre id='vlm'></pre></div></section><script>let token='';file.onchange=()=>{if(file.files[0])preview.src=URL.createObjectURL(file.files[0])};async function run(){if(!file.files[0]){state.textContent='请先选择图片';return}state.textContent='登录中';let l=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'teacher',password:'stage3-demo'})});token=(await l.json()).access_token;let f=new FormData();f.append('file',file.files[0]);let u=await fetch('/api/upload',{method:'POST',headers:{Authorization:'Bearer '+token},body:f});if(!u.ok){state.textContent='上传失败';return}let upload=await u.json();let c=await fetch('/api/compare',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(upload)});let t=await c.json();state.textContent='任务 '+t.task_id+' 执行中';let timer=setInterval(async()=>{let r=await fetch('/api/tasks/'+t.task_id,{headers:{Authorization:'Bearer '+token}});let x=await r.json();state.textContent=x.status+(x.error?' | '+x.error:'');yolo.textContent=JSON.stringify(x.yolo,null,2);vlm.textContent=JSON.stringify(x.vlm,null,2);if(['success','partial_success','failed'].includes(x.status))clearInterval(timer)},1000)}</script></html>""")
