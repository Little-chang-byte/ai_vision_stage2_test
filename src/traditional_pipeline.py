import json, time
from pathlib import Path
from collections import Counter
from ultralytics import YOLO
class YoloDetector:
    def __init__(self, model_name="yolo11n.pt"):
        self.model_name=model_name; self.model=YOLO(model_name)
    def detect(self,image_path,image_id,output_dir="results/traditional",conf=0.25):
        p=Path(image_path); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
        if not p.exists(): raise FileNotFoundError(f"image does not exist: {p}")
        started=time.perf_counter(); result=self.model.predict(source=str(p),conf=conf,verbose=False)[0]; elapsed=time.perf_counter()-started
        objects=[]; names=result.names
        if result.boxes is not None:
            for box,cls,score in zip(result.boxes.xyxy.tolist(),result.boxes.cls.tolist(),result.boxes.conf.tolist()):
                objects.append({"name":names[int(cls)],"count":1,"confidence":round(float(score),4),"bbox":[round(float(x),2) for x in box]})
        payload={"image_id":image_id,"method":"YOLO","model":self.model_name,"objects":objects,"counts":dict(Counter(x["name"] for x in objects)),"runtime_seconds":round(elapsed,4),"error":None}
        json.dump(payload,open(out/f"{image_id}.json","w",encoding="utf-8"),ensure_ascii=False,indent=2); result.save(filename=str(out/f"{image_id}.jpg")); return payload

def run_yolo(image_path,image_id,output_dir="results/traditional",model_name="yolo11n.pt",conf=0.25): return YoloDetector(model_name).detect(image_path,image_id,output_dir,conf)
