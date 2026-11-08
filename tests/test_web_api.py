import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Import against an isolated database even before setUp runs.
IMPORT_TEMP = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(IMPORT_TEMP.name) / "import.db")
os.environ["UPLOAD_DIR"] = str(Path(IMPORT_TEMP.name) / "uploads")
os.environ["RESULT_DIR"] = str(Path(IMPORT_TEMP.name) / "results")
from src import web_app as w

def tearDownModule():
    w.engine.dispose()
    IMPORT_TEMP.cleanup()



def fixtures():
    yolo = {"image_id": "test", "method": "YOLO", "model": "yolo11n.pt", "objects": [{"name": "mouse", "count": 1, "confidence": 0.9, "bbox": [0, 0, 10, 10]}], "counts": {"mouse": 1}, "runtime_seconds": 0.1, "error": None}
    vlm = {"image_id": "test", "method": "VLM", "model": "qwen3-vl:4b", "objects": [{"name": "mouse", "count": 1, "uncertain": False}], "counts": {"mouse": 1}, "runtime_seconds": 0.2, "done": True, "done_reason": "stop", "error": None, "attempts": [{"attempt": 1, "status": "verified"}]}
    return yolo, vlm


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = create_engine("sqlite:///" + str(self.root / "test.db"), connect_args={"check_same_thread": False})
        w.Base.metadata.create_all(self.engine)
        self.upload_dir = self.root / "uploads"
        self.result_dir = self.root / "results"
        self.upload_dir.mkdir()
        self.result_dir.mkdir()
        self.patchers = [
            patch.object(w, "SessionLocal", sessionmaker(bind=self.engine, expire_on_commit=False)),
            patch.object(w, "UPLOAD_DIR", self.upload_dir), patch.object(w, "RESULT_DIR", self.result_dir),
            patch.object(w, "JWT_SECRET", "isolated-test-secret-at-least-32-bytes"),
            patch.object(w, "DEMO_PASSWORD_HASH", w.hash_password("test-password")),
            patch.dict(os.environ, {"TASK_MODE": "local"}),
        ]
        for item in self.patchers:
            item.start()
        self.client = TestClient(w.app)
        self.headers = {"Authorization": "Bearer " + self.client.post("/api/auth/login", json={"username": w.DEMO_USER, "password": "test-password"}).json()["access_token"]}
        data = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(data, format="PNG")
        self.data = data.getvalue()

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patchers):
            item.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def upload(self):
        response = self.client.post("/api/upload", headers=self.headers, files={"file": ("test.png", self.data, "image/png")})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def execute(self, yolo, vlm):
        with patch.object(w, "YoloDetector") as detector, patch.object(w, "run_vlm", return_value=vlm):
            detector.return_value.detect.return_value = yolo
            response = self.client.post("/api/compare", headers=self.headers, json=self.upload())
        self.assertEqual(response.status_code, 200)
        task_id = response.json()["task_id"]
        return self.client.get("/api/tasks/" + task_id, headers=self.headers).json()

    def test_four_model_outcomes_and_database(self):
        for ys, vs, expected in [(True, True, "success"), (True, False, "partial_success"), (False, True, "partial_success"), (False, False, "failed")]:
            with self.subTest(yolo=ys, vlm=vs):
                y, v = fixtures()
                if not ys:
                    y["counts"] = {"mouse": -1}
                if not vs:
                    v["done_reason"] = "length"
                body = self.execute(y, v)
                self.assertEqual(body["status"], expected)
                self.assertEqual(body["yolo_status"], "success" if ys else "failed")
                self.assertEqual(body["vlm_status"], "success" if vs else "failed")
                self.assertEqual(body["comparison"]["yolo_counts"], {"mouse": 1} if ys else {})
                self.assertEqual(body["comparison"]["vlm_counts"], {"mouse": 1} if vs else {})
                if not ys or not vs:
                    self.assertTrue(body["error"])
                with w.SessionLocal() as db:
                    saved = db.get(w.Task, body["task_id"])
                    self.assertEqual(saved.status, expected)
                    self.assertEqual(json.loads(saved.yolo_result), y)
                    self.assertEqual(json.loads(saved.vlm_result), v)

    def test_model_exceptions_independent(self):
        y, v = fixtures()
        with patch.object(w, "YoloDetector", side_effect=RuntimeError("YOLO unavailable")), patch.object(w, "run_vlm", return_value=v):
            response = self.client.post("/api/compare", headers=self.headers, json=self.upload())
        body = self.client.get("/api/tasks/" + response.json()["task_id"], headers=self.headers).json()
        self.assertEqual(body["status"], "partial_success")
        self.assertIn("YOLO unavailable", body["error"])

    def test_hash_binding_and_path_rejection(self):
        payload = self.upload()
        for bad in [{"image_path": payload["image_path"]}, dict(payload, image_sha256="0"*64), dict(payload, image_path=str(self.root / "missing.png")), dict(payload, image_path=str(self.root / "../outside.png"))]:
            self.assertEqual(self.client.post("/api/compare", headers=self.headers, json=bad).status_code, 400)
        Path(payload["image_path"]).write_bytes(b"modified")
        self.assertEqual(self.client.post("/api/compare", headers=self.headers, json=payload).status_code, 400)

    def test_duplicate_upload_and_invalid_image(self):
        self.assertEqual(self.upload(), self.upload())
        response = self.client.post("/api/upload", headers=self.headers, files={"file": ("fake.png", b"not-image", "image/png")})
        self.assertEqual(response.status_code, 415)

    def test_symlink_upload_rejected(self):
        target = self.root / "outside.png"
        target.write_bytes(b"must remain")
        link = self.upload_dir / (hashlib.sha256(self.data).hexdigest() + ".png")
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest("Windows symlink permission unavailable: " + str(exc))
        response = self.client.post("/api/upload", headers=self.headers, files={"file": ("test.png", self.data, "image/png")})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(target.read_bytes(), b"must remain")

    def test_login_and_jwt_cases(self):
        self.assertEqual(self.client.get("/api/history").status_code, 401)
        self.assertEqual(self.client.get("/api/history", headers=self.headers).status_code, 200)
        for claims, key in [({}, w.JWT_SECRET), ({"sub": ""}, w.JWT_SECRET), ({"sub": "other"}, w.JWT_SECRET), ({"sub": w.DEMO_USER}, "wrong-key-at-least-32-characters-long"), ({"sub": w.DEMO_USER, "exp": datetime.now(timezone.utc)-timedelta(seconds=1)}, w.JWT_SECRET)]:
            encoded = jwt.encode(claims, key, algorithm="HS256")
            self.assertEqual(self.client.get("/api/history", headers={"Authorization": "Bearer "+encoded}).status_code, 401)
        for password in ["wrong", ""]:
            self.assertEqual(self.client.post("/api/auth/login", json={"username": w.DEMO_USER, "password": password}).status_code, 401)
        with patch.object(w, "DEMO_PASSWORD_HASH", ""):
            self.assertEqual(self.client.post("/api/auth/login", json={}).status_code, 503)

    def test_password_format(self):
        encoded = w.hash_password("correct")
        self.assertTrue(w.verify_password("correct", encoded))
        self.assertFalse(w.verify_password("wrong", encoded))
        for value in [None, "", "bad", encoded+"$extra", encoded.replace("310000", "1000001"), encoded.replace("310000", "99"), encoded.replace("310000", "NaN"), "pbkdf2_sha256$310000$zz$00"]:
            self.assertFalse(w.verify_password("correct", value))

    def test_crud_and_protected_images(self):
        body = self.execute(*fixtures())
        path = "/api/tasks/" + body["task_id"]
        self.assertEqual(self.client.get(path+"/image/original").status_code, 401)
        self.assertEqual(self.client.get(path+"/image/original", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.patch(path, headers=self.headers, json={"note":"reviewed"}).json()["note"], "reviewed")
        self.assertEqual(self.client.delete(path, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.delete(path+"?confirm=true", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 404)

    def test_queue_publish_and_failure(self):
        from src.queue_app import execute_task
        with patch.dict(os.environ, {"TASK_MODE":"celery"}), patch.object(execute_task, "apply_async") as publish:
            response = self.client.post("/api/compare", headers=self.headers, json=self.upload())
            task_id = response.json()["task_id"]
            publish.assert_called_once_with(args=[task_id], task_id=task_id, retry=False)
            self.assertEqual(self.client.get("/api/tasks/"+task_id, headers=self.headers).json()["status"], "pending")
        with patch.dict(os.environ, {"TASK_MODE":"celery"}), patch.object(execute_task, "apply_async", side_effect=ConnectionError("offline")):
            response = self.client.post("/api/compare", headers=self.headers, json=self.upload())
            self.assertEqual(response.status_code, 503)
            task_id = response.json()["detail"]["task_id"]
            self.assertIn("QUEUE_UNAVAILABLE", self.client.get("/api/tasks/"+task_id, headers=self.headers).json()["error"])

    def test_duplicate_delivery_does_not_run_models_twice(self):
        body = self.execute(*fixtures())
        with patch.object(w, "YoloDetector") as runner:
            w.run_task(body["task_id"])
            runner.assert_not_called()

    def test_worker_interruption_requires_explicit_recovery(self):
        from src.queue_app import execute_task, mark_interrupted
        with patch.dict(os.environ, {"TASK_MODE":"celery"}), patch.object(execute_task, "apply_async"):
            response = self.client.post("/api/compare", headers=self.headers, json=self.upload())
        task_id = response.json()["task_id"]
        mark_interrupted.run(task_id)
        body = self.client.get("/api/tasks/"+task_id, headers=self.headers).json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("WORKER_INTERRUPTED", body["error"])
