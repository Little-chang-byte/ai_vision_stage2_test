import json
import sys
import unittest
from unittest.mock import patch
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


    @patch.object(web_app.YoloDetector, "detect", return_value={"method": "YOLO", "counts": {"mouse": 2}})
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
