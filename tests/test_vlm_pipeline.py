import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vlm_pipeline as v
from traditional_pipeline import validate_yolo_result
from comparison import compare_row, save_comparison

VALID_YOLO={"method":"YOLO","model":"test","objects":[],"counts":{},"runtime_seconds":0.1,"error":None}

class VlmRegressionTests(unittest.TestCase):
    def test_yolo_schema_validation(self):
        valid = {"method":"YOLO","model":"test","objects":[],"counts":{},"runtime_seconds":0.1,"error":None}
        self.assertTrue(validate_yolo_result(valid))
        detection = {"method":"YOLO","model":"test","objects":[{"name":"mouse","count":1,"confidence":0.9,"bbox":[0,0,1,1]}],"counts":{"mouse":1},"runtime_seconds":0.1,"error":None}
        self.assertTrue(validate_yolo_result(detection))
        for bad in [dict(detection, counts={}), dict(detection, objects=[{"name":"mouse","count":1,"confidence":2,"bbox":[0,0,1,1]}]), dict(detection, objects=[{"name":"mouse","count":1,"confidence":0.9,"bbox":[0,0,float('nan'),1]}])]:
            with self.assertRaises(ValueError): validate_yolo_result(bad)

    def test_ollama_base_url_is_configurable(self):
        old = os.environ.get("OLLAMA_BASE_URL")
        calls = []
        class Response:
            def raise_for_status(self): pass
            def json(self): return {"ok": True}
        try:
            os.environ["OLLAMA_BASE_URL"] = "http://example.test///"
            with patch.object(v.requests, "post", side_effect=lambda url, **kwargs: (calls.append(url) or Response())):
                v.request("p", "data")
            self.assertEqual(calls, ["http://example.test/api/chat"])
        finally:
            if old is None: os.environ.pop("OLLAMA_BASE_URL", None)
            else: os.environ["OLLAMA_BASE_URL"] = old
    def test_ollama_configuration_boundaries(self):
        for url in ["http://127.0.0.1:11434", "http://host.docker.internal:11434/", "http://example.test///"]:
            with patch.dict(os.environ, {"OLLAMA_BASE_URL":url, "VLM_TIMEOUT_SECONDS":"120"}), patch.object(v.requests, "post") as post:
                post.return_value.json.return_value = {}
                v.request("p", "data")
                self.assertEqual(post.call_args.args[0], url.rstrip("/")+"/api/chat")
                self.assertEqual(post.call_args.kwargs["timeout"], 120)
        for url in ["", "bad-url", "ftp://bad"]:
            with patch.dict(os.environ, {"OLLAMA_BASE_URL":url}), self.assertRaises(ValueError):
                v.request("p", "data")
        for timeout in ["0", "-1", "not-a-number", "nan", "inf"]:
            with patch.dict(os.environ, {"VLM_TIMEOUT_SECONDS":timeout}), self.assertRaises(ValueError):
                v.request("p", "data")

    def test_duplicate_counts(self):
        self.assertEqual(v.aggregate_objects([{"name":"mouse","count":1},{"name":"mouse","count":1}])[1], {"mouse":2})
        self.assertEqual(v.aggregate_objects([{"name":"mouse","count":1},{"name":"mouse","count":2},{"name":"keyboard","count":1},{"name":"mouse","count":1}])[1], {"mouse":4,"keyboard":1})
    def test_alias_and_empty(self):
        self.assertEqual(v.aggregate_objects([{"name":"鼠标","count":1},{"name":"computer mouse","count":2},{"name":"keyboard","count":1}])[1], {"mouse":3,"keyboard":1})
        self.assertEqual(v.validate_payload({"objects":[]}), ([],{}))
    def test_invalid_values(self):
        for raw in ["", "   ", None, "{}", '{"objects":null}', '{"objects":"mouse"}', '{"objects":["mouse"]}', '{"objects":[{"name":"mouse","count":-1}]}', '{"objects":[{"name":"mouse","count":1.5}]}', '{"objects":[{"name":"mouse","count":"two"}]}', '{"objects":[{"name":"mouse","count":true}]}', '{"objects":[{"name":"mouse"}]}', '{"objects":[{"count":1}]}', '{"objects":[{"name":"","count":1}]}', '{"objects":[{"name":"mouse","count":1}']:
            with self.assertRaises(ValueError):
                v.validate_payload(v.parse_json(raw))
    def test_truncated_json_rejected(self):
        with self.assertRaises(ValueError):
            v.parse_json('{"objects":[{"name":"mouse","count":1}')
    def test_ids_use_same_retry_rules(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "same.jpg"
            image.write_bytes(b"image")
            old_retries, old_backoff, old_request = v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS, v.request
            v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS = 2, 0
            v.request = lambda prompt, data: {"model":"qwen3-vl:4b", "done":True, "done_reason":"stop", "message":{"content": json.dumps({"objects":["mouse"]})}}
            try:
                a = v.run_vlm(image, "D001", Path(td) / "a")
                b = v.run_vlm(image, "TEST_001", Path(td) / "b")
                c = v.run_vlm(image, "RANDOM_123", Path(td) / "c")
            finally:
                v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS, v.request = old_retries, old_backoff, old_request
            self.assertEqual([x["attempt"] for x in a["attempts"]], [1,2,3])
            self.assertEqual([x["attempt"] for x in b["attempts"]], [1,2,3])
            self.assertEqual(a["error"], b["error"])
            self.assertEqual([x["attempt"] for x in a["attempts"]], [x["attempt"] for x in c["attempts"]])
            self.assertEqual(a["error"], c["error"])

    def test_comparison_requires_verified_record(self):
        invalid = {"image_id":"x", "method":"VLM", "objects":["mouse"], "counts":{"mouse":1}, "runtime_seconds":1, "error":None}
        self.assertEqual(compare_row("x", VALID_YOLO, invalid)["vlm_status"], "error")

    def test_comparison_accepts_complete_empty_result_and_writes_consistent_files(self):
        valid = {"image_id":"x", "method":"VLM", "model":"qwen3-vl:4b", "objects":[], "counts":{}, "runtime_seconds":1, "done":True, "done_reason":"stop", "error":None, "attempts":[{"attempt":1,"status":"verified"}]}
        row = compare_row("x", VALID_YOLO, valid)
        self.assertEqual(row["vlm_status"], "verified")
        with tempfile.TemporaryDirectory() as td:
            save_comparison([row], td)
            self.assertIn('"vlm_status": "verified"', (Path(td) / "comparison.json").read_text(encoding="utf-8"))
            self.assertIn("verified", (Path(td) / "comparison.csv").read_text(encoding="utf-8-sig"))

    def test_mocked_production_flow_rejects_invalid_objects_before_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / "same.jpg"
            image.write_bytes(b"image")
            old_request, old_retries, old_backoff = v.request, v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS
            v.request = lambda prompt, data: {"model":"qwen3-vl:4b", "done":True, "done_reason":"stop", "message":{"content": json.dumps({"objects":["mouse"]})}}
            v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS = 0, 0
            try:
                result = v.run_vlm(image, "FLOW", Path(td) / "vlm")
            finally:
                v.request, v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS = old_request, old_retries, old_backoff
            row = compare_row("FLOW", VALID_YOLO, result)
            self.assertEqual(result["error"], "VLM_SCHEMA_VALIDATION_FAILED")
            self.assertEqual(row["vlm_status"], "error")
            self.assertEqual(row["vlm_counts"], {})

if __name__ == "__main__": unittest.main()



