import base64, json, os, time
from collections import OrderedDict
from pathlib import Path
import requests
import math
from urllib.parse import urlparse

PROMPT = 'List visible physical objects. Return JSON only: {"objects":[{"name":"short English category","count":1,"uncertain":false}]}. Do not describe text or explain reasoning.'
RETRY_PROMPT = 'Return JSON only: {"objects":[{"name":"object","count":1,"uncertain":false}]}. List clearly visible physical objects. Do not explain reasoning.'
MAX_RETRIES = int(os.getenv("VLM_MAX_RETRIES", "2"))
RETRY_BACKOFF_SECONDS = float(os.getenv("VLM_RETRY_BACKOFF_SECONDS", "1"))
RETRYABLE_ERRORS = {"VLM_EMPTY_RESPONSE", "VLM_INVALID_JSON", "VLM_INCOMPLETE_RESPONSE", "VLM_SCHEMA_VALIDATION_FAILED", "VLM_INVALID_COUNT", "VLM_MISSING_REQUIRED_FIELD"}

ALIASES = {"computer mouse": "mouse", "wireless mouse": "mouse", "鼠标": "mouse", "键盘": "keyboard", "耳机盒": "earbuds case", "充电宝": "power bank", "书": "book", "教材": "book", "保温杯": "cup"}

def normalize_name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("VLM_INVALID_NAME")
    clean = " ".join(name.strip().lower().split())
    return ALIASES.get(clean, clean)

def aggregate_objects(objects):
    totals = OrderedDict()
    merged = OrderedDict()
    for item in objects:
        if isinstance(item, dict):
            if "name" not in item or "count" not in item:
                raise ValueError("VLM_MISSING_REQUIRED_FIELD")
            name, count = normalize_name(item["name"]), item["count"]
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise ValueError("VLM_INVALID_COUNT")
            uncertain = bool(item.get("uncertain", False))
        else:
            raise ValueError("VLM_SCHEMA_VALIDATION_FAILED")
        totals[name] = totals.get(name, 0) + count
        merged[name] = {"name": name, "count": totals[name], "uncertain": bool(merged.get(name, {}).get("uncertain", False) or uncertain)}
    return list(merged.values()), dict(totals)

def validate_result_record(result):
    if not isinstance(result, dict):
        raise ValueError("VLM_RESULT_SCHEMA_VALIDATION_FAILED")
    required = {"image_id", "method", "model", "objects", "counts", "runtime_seconds", "done", "done_reason", "error", "attempts"}
    if not required.issubset(result):
        raise ValueError("VLM_RESULT_MISSING_REQUIRED_FIELD")
    if result["method"] != "VLM" or not isinstance(result["image_id"], str):
        raise ValueError("VLM_RESULT_SCHEMA_VALIDATION_FAILED")
    if result["error"] is not None or result["done"] is not True or result["done_reason"] not in (None, "stop"):
        raise ValueError("VLM_RESULT_NOT_VERIFIED")
    if not isinstance(result["objects"], list) or not isinstance(result["counts"], dict):
        raise ValueError("VLM_RESULT_SCHEMA_VALIDATION_FAILED")
    objects, counts = aggregate_objects(result["objects"])
    if counts != result["counts"] or objects != result["objects"]:
        raise ValueError("VLM_RESULT_COUNTS_MISMATCH")
    if not isinstance(result["attempts"], list) or not result["attempts"]:
        raise ValueError("VLM_RESULT_MISSING_REQUIRED_FIELD")
    return True

def validate_payload(parsed):
    if not isinstance(parsed, dict) or "objects" not in parsed or not isinstance(parsed["objects"], list):
        raise ValueError("VLM_SCHEMA_VALIDATION_FAILED" if isinstance(parsed, dict) else "VLM_SCHEMA_VALIDATION_FAILED")
    objects, counts = aggregate_objects(parsed["objects"])
    return objects, counts

def parse_json(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("VLM_EMPTY_RESPONSE")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("VLM_INVALID_JSON") from exc
    return parsed

def request(prompt, data):
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("OLLAMA_BASE_URL must be an HTTP URL")
    timeout = float(os.getenv("VLM_TIMEOUT_SECONDS", "120"))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("VLM_TIMEOUT_SECONDS must be positive")
    response = requests.post(f"{base_url}/api/chat", json={"model": os.getenv("VLM_MODEL", "qwen3-vl:4b"), "messages": [{"role": "user", "content": prompt, "images": [data]}], "stream": False, "think": False, "format": "json", "options": {"temperature": 0, "num_predict": int(os.getenv("VLM_NUM_PREDICT", "4000"))}}, timeout=timeout)
    response.raise_for_status()
    return response.json()

def _failure(image_id, body, attempts, started, error):
    return {"image_id": image_id, "method": "VLM", "model": (body or {}).get("model"), "objects": [], "counts": {}, "runtime_seconds": round(time.perf_counter() - started, 4), "done": (body or {}).get("done"), "done_reason": (body or {}).get("done_reason"), "raw_content_length": len(((body or {}).get("message") or {}).get("content") or ""), "error": error, "attempts": attempts}

def run_vlm(image_path, image_id, output_dir="results/vlm"):
    path, out = Path(image_path), Path(output_dir)
    if not path.is_file():
        return _failure(image_id, {}, [], time.perf_counter(), "VLM_IMAGE_NOT_FOUND")
    out.mkdir(parents=True, exist_ok=True)
    data, started, attempts, body = base64.b64encode(path.read_bytes()).decode(), time.perf_counter(), [], {}
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            body = request(PROMPT if attempt == 1 else RETRY_PROMPT, data)
            with open(out / f"{image_id}_attempt_{attempt}_raw.json", "w", encoding="utf-8") as evidence:
                json.dump(body, evidence, ensure_ascii=False, indent=2)
            message = body.get("message")
            raw = message.get("content") if isinstance(message, dict) else None
            done_reason = body.get("done_reason")
            done = body.get("done")
            if not isinstance(message, dict) or not isinstance(raw, str) or not raw.strip():
                raise ValueError("VLM_EMPTY_RESPONSE")
            if done is not True or done_reason not in (None, "stop"):
                raise ValueError("VLM_INCOMPLETE_RESPONSE" if done_reason != "length" else "MAX_OUTPUT_REACHED")
            parsed = parse_json(raw)
            objects, counts = validate_payload(parsed)
            attempts.append({"attempt": attempt, "status": "verified", "error_type": None, "done_reason": done_reason, "raw_content_length": len(raw)})
            payload = {"image_id": image_id, "method": "VLM", "model": body.get("model"), "objects": objects, "counts": counts, "runtime_seconds": round(time.perf_counter()-started, 4), "done": done, "done_reason": done_reason, "raw_content_length": len(raw), "error": None, "attempts": attempts}
            validate_result_record(payload)
            break
        except requests.RequestException as exc:
            error = "VLM_REQUEST_FAILED"; attempts.append({"attempt": attempt, "status": "error", "error_type": error, "detail": str(exc)})
        except ValueError as exc:
            error = str(exc); attempts.append({"attempt": attempt, "status": "error", "error_type": error, "done_reason": body.get("done_reason"), "raw_content_length": len(((body.get("message") or {}).get("content") or ""))})
        if attempt > MAX_RETRIES or error not in RETRYABLE_ERRORS and error != "MAX_OUTPUT_REACHED":
            payload = _failure(image_id, body, attempts, started, error)
            break
        time.sleep(RETRY_BACKOFF_SECONDS)
    with open(out / f"{image_id}_raw.json", "w", encoding="utf-8") as raw_file:
        json.dump(body, raw_file, ensure_ascii=False, indent=2)
    with open(out / f"{image_id}.json", "w", encoding="utf-8") as result_file:
        json.dump(payload, result_file, ensure_ascii=False, indent=2)
    return payload
