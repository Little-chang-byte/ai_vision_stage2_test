import base64, json, os, time
from pathlib import Path
from openai import OpenAI
PROMPT = 'Analyze the image. Return JSON only, exactly {\"objects\":[]} . Add visible objects with English name, count, and short evidence. Do not guess.'
def run_vlm(image_path, image_id, output_dir='results/vlm'):
    key=os.getenv('VLM_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not key: raise RuntimeError('缺少 VLM_API_KEY 或 OPENAI_API_KEY')
    p=Path(image_path)
    if not p.exists(): raise FileNotFoundError(f'image does not exist: {p}')
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    client=OpenAI(api_key=key, base_url=os.getenv('VLM_BASE_URL') or None, timeout=float(os.getenv('VLM_TIMEOUT_SECONDS','120')), max_retries=1)
    data=base64.b64encode(p.read_bytes()).decode(); started=time.perf_counter()
    resp=client.chat.completions.create(model=os.getenv('VLM_MODEL','gpt-4o-mini'),temperature=0,max_tokens=300,messages=[{'role':'user','content':[{'type':'text','text':PROMPT},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+data}}]}])
    elapsed=time.perf_counter()-started; raw=(resp.choices[0].message.content or '').strip()
    if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
    parsed=None
    for i,ch in enumerate(raw):
        if ch=='{':
            try: parsed=json.JSONDecoder().raw_decode(raw[i:])[0]; break
            except json.JSONDecodeError: pass
    if parsed is None: raise ValueError('VLM response did not contain valid JSON')
    parsed=parsed; objects=parsed.get('objects',[])
    payload={'image_id':image_id,'method':'VLM','model':os.getenv('VLM_MODEL','gpt-4o-mini'),'objects':objects,'counts':{o['name']:o.get('count',1) for o in objects},'runtime_seconds':round(elapsed,4),'usage':getattr(resp,'usage',None) and resp.usage.model_dump(),'error':None}
    json.dump(payload,open(out/f'{image_id}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); json.dump({'raw':raw},open(out/f'{image_id}_raw.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); return payload

