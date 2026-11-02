import csv,json
from pathlib import Path
from PIL import Image,ImageDraw

def position(bbox,w,h):
 x=(bbox[0]+bbox[2])/2; y=(bbox[1]+bbox[3])/2
 return ("左" if x<w/3 else "右" if x>w*2/3 else "中")+("上" if y<h/3 else "下" if y>h*2/3 else "央")
def search_yolo(detector,image_path,image_id,query,output_dir="results/search",conf=0.25):
 aliases={"瓶子":"bottle","杯子":"cup","键盘":"keyboard","鼠标":"mouse","手机":"cell phone","剪刀":"scissors","人":"person","公交车":"bus"}; target=aliases.get(query,query.lower()); result=detector.detect(image_path,image_id,output_dir,conf); im=Image.open(image_path).convert("RGB"); draw=ImageDraw.Draw(im); found=[]
 for o in result["objects"]:
  if o["name"].lower()==target:
   b=o["bbox"]; found.append({"name":o["name"],"confidence":o["confidence"],"bbox":b,"position":position(b,*im.size)}); draw.rectangle(b,outline="red",width=5); draw.text((b[0],max(0,b[1]-20)),f"{o['name']} {o['confidence']:.2f}",fill="red")
 payload={"query":query,"normalized_query":target,"found":bool(found),"count":len(found),"objects":found,"runtime_seconds":result["runtime_seconds"],"error":None if found else "未检测到目标或模型不支持该类别"}
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); json.dump(payload,open(out/f"{image_id}_{target}.json","w",encoding="utf-8"),ensure_ascii=False,indent=2); im.save(out/f"{image_id}_{target}.jpg"); return payload
