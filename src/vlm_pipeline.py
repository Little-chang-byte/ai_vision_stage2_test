import base64, json, os, time
from pathlib import Path
from openai import OpenAI
PROMPT = "识别图片中的桌面物品，返回严格 JSON：{objects:[{name,count,evidence}]}。只报告能从图片确认的物品；不确定时说明不确定，不要编造。"
def run_vlm(image_path, image_id, output_dir="results/vlm"):
    key=os.getenv("VLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key: raise RuntimeError("缺少 VLM_API_KEY 或 OPENAI_API_KEY，无法执行真实多模态推理")
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    client=OpenAI(api_key=key, base_url=os.getenv("VLM_BASE_URL") or None)
    data=base64.b64encode(Path(image_path).read_bytes()).decode(); started=time.perf_counter()
    resp=client.chat.completions.create(model=os.getenv("VLM_MODEL","gpt-4o-mini"), temperature=0, response_format={"type":"json_object"}, messages=[{"role":"user","content":[{"type":"text","text":PROMPT},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+data}}]}])
    elapsed=time.perf_counter()-started; raw=resp.choices[0].message.content; parsed=json.loads(raw)
    payload={"image_id":image_id,"method":"VLM","model":os.getenv("VLM_MODEL","gpt-4o-mini"),"objects":parsed.get("objects",[]),"runtime_seconds":round(elapsed,4),"usage":getattr(resp,"usage",None) and resp.usage.model_dump()}
    json.dump(payload,open(out/f"{image_id}.json","w",encoding="utf-8"),ensure_ascii=False,indent=2); json.dump({"raw":raw},open(out/f"{image_id}_raw.json","w",encoding="utf-8"),ensure_ascii=False,indent=2); return payload

