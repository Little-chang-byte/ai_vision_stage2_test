import json, time
from pathlib import Path
from collections import Counter
from ultralytics import YOLO

def run_yolo(image_path, image_id, output_dir="results/traditional", model_name="yolo11n.pt", conf=0.25):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    model = YOLO(model_name)
    started = time.perf_counter()
    result = model.predict(source=str(image_path), conf=conf, verbose=False)[0]
    elapsed = time.perf_counter() - started
    objects=[]; names = result.names
    if result.boxes is not None:
        for box, cls, score in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
            objects.append({"name": names[int(cls)], "count": 1, "confidence": round(float(score),4), "bbox": [round(float(x),2) for x in box]})
    counts = Counter(x["name"] for x in objects)
    payload={"image_id":image_id,"method":"YOLO","model":model_name,"objects":objects,"counts":dict(counts),"runtime_seconds":round(elapsed,4)}
    json.dump(payload, open(out/f"{image_id}.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    result.save(filename=str(out/f"{image_id}.jpg")); return payload

