import json
import sys
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import jwt
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import web_app


client = TestClient(web_app.app)
web_app.JWT_SECRET = "test-secret-with-more-than-32-bytes"
web_app.DEMO_PASSWORD_HASH = web_app.hash_password("stage3-demo")


def token():
    response = client.post("/api/auth/login", json={"username": "teacher", "password": "stage3-demo"})
    assert response.status_code == 200
    return response.json()["access_token"]


class WebApiTests(unittest.TestCase):
    def test_health_and_authentication(self):
        self.assertEqual(client.get("/health").json()["status"], "ok")
        self.assertEqual(client.get("/api/history").status_code, 401)
        self.assertTrue(token())


    @patch.object(web_app.YoloDetector, "detect", return_value={"method": "YOLO", "model": "test", "objects": [{"name": "mouse", "count": 1, "confidence": 0.9, "bbox": [0, 0, 1, 1]}, {"name": "mouse", "count": 1, "confidence": 0.8, "bbox": [1, 1, 2, 2]}], "counts": {"mouse": 2}, "runtime_seconds": 0.1, "error": None})
    @patch.object(web_app, "run_vlm", return_value={"method": "VLM", "objects": [{"name": "mouse", "count": 2}], "counts": {"mouse": 2}, "error": None})
    def test_upload_and_compare_with_model_adapters(self, _vlm, _yolo):
        headers = {"Authorization": f"Bearer {token()}"}
        upload = client.post("/api/upload", headers=headers, files={"file": ("same.jpg", b"real-input-bytes", "image/jpeg")})
        self.assertEqual(upload.status_code, 200)
        uploaded = upload.json()
        created = client.post("/api/compare", headers=headers, json=uploaded)
        self.assertEqual(created.status_code, 200)
        result = client.get(f"/api/tasks/{created.json()['task_id']}", headers=headers)
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["image_sha256"], uploaded["image_sha256"])
        self.assertEqual(body["yolo"]["counts"], {"mouse": 2})
        self.assertEqual(body["vlm"]["counts"], {"mouse": 2})

    def test_server_rejects_tampered_hash_and_paths(self):
        headers = {"Authorization": f"Bearer {token()}"}
        upload = client.post("/api/upload", headers=headers, files={"file": ("same.jpg", b"immutable", "image/jpeg")}).json()
        forged = dict(upload, image_sha256="0" * 64)
        self.assertEqual(client.post("/api/compare", headers=headers, json=forged).status_code, 400)
        outside = {"image_path": str(Path(__file__).resolve()), "image_sha256": ""}
        self.assertEqual(client.post("/api/compare", headers=headers, json=outside).status_code, 400)

    def test_hash_is_required_and_jwt_subject_is_checked(self):
        headers = {"Authorization": f"Bearer {token()}"}
        upload = client.post("/api/upload", headers=headers, files={"file": ("same.jpg", b"required-hash", "image/jpeg")}).json()
        missing = dict(upload); missing.pop("image_sha256")
        self.assertEqual(client.post("/api/compare", headers=headers, json=missing).status_code, 400)
        wrong = jwt.encode({"sub": "other", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, web_app.JWT_SECRET, algorithm="HS256")
        self.assertEqual(client.get("/api/history", headers={"Authorization": f"Bearer {wrong}"}).status_code, 401)

    def test_password_hash_rejects_malformed_parameters(self):
        self.assertTrue(web_app.verify_password("stage3-demo", web_app.DEMO_PASSWORD_HASH))
        self.assertFalse(web_app.verify_password("wrong", web_app.DEMO_PASSWORD_HASH))
        for value in [None, "", "bad", "pbkdf2_sha512$310000$00$00", "pbkdf2_sha256$99$00$00", "pbkdf2_sha256$1000001$00$00", "pbkdf2_sha256$310000$zz$00"]:
            self.assertFalse(web_app.verify_password("stage3-demo", value))
