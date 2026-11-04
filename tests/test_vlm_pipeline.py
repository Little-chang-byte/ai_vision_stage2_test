import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vlm_pipeline as v

class VlmRegressionTests(unittest.TestCase):
    def test_duplicate_counts(self):
        self.assertEqual(v.aggregate_objects([{"name":"mouse","count":1},{"name":"mouse","count":1}])[1], {"mouse":2})
        self.assertEqual(v.aggregate_objects([{"name":"mouse","count":1},{"name":"mouse","count":2},{"name":"keyboard","count":1},{"name":"mouse","count":1}])[1], {"mouse":4,"keyboard":1})
    def test_alias_and_empty(self):
        self.assertEqual(v.aggregate_objects([{"name":"鼠标","count":1},{"name":"computer mouse","count":2},{"name":"keyboard","count":1}])[1], {"mouse":3,"keyboard":1})
        self.assertEqual(v.validate_payload({"objects":[]}), ([],{}))
    def test_invalid_values(self):
        for raw in ["", "   ", None, "{}", '{"objects":null}', '{"objects":"mouse"}', '{"objects":[{"name":"mouse","count":-1}]}', '{"objects":[{"name":"mouse","count":1.5}]}', '{"objects":[{"name":"mouse","count":"two"}]}', '{"objects":[{"name":"mouse","count":true}]}', '{"objects":[{"name":"mouse"}]}', '{"objects":[{"name":"mouse","count":1}']:
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
            v.request = lambda prompt, data: {"done":True,"done_reason":"stop","message":{"content":""}}
            try:
                a = v.run_vlm(image, "D001", Path(td) / "a")
                b = v.run_vlm(image, "TEST_001", Path(td) / "b")
            finally:
                v.MAX_RETRIES, v.RETRY_BACKOFF_SECONDS, v.request = old_retries, old_backoff, old_request
            self.assertEqual([x["attempt"] for x in a["attempts"]], [1,2,3])
            self.assertEqual([x["attempt"] for x in b["attempts"]], [1,2,3])
            self.assertEqual(a["error"], b["error"])

if __name__ == "__main__": unittest.main()
