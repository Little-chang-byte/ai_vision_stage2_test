import base64,json,os,time
from pathlib import Path
from openai import OpenAI
PROMPT='Return JSON only with schema {"objects":[{"name":"english name","count":1,"evidence":"visible evidence"}]}. Analyze only visible objects; do not guess.'
def parse_json(raw):
 raw=(raw or '').strip()
 if raw.startswith('```'): raw=raw.split('\n',1)[-1].rsplit('```',1)[0].strip()
 decoder=json.JSONDecoder()
 for i,ch in enumerate(raw):
  if ch=='{':
   try: return decoder.raw_decode(raw[i:])[0]
   except json.JSONDecodeError: continue
 raise ValueError('VLM response did not contain valid JSON')
def run_vlm(image_path,image_id,output_dir='results/vlm'):
 key=os.getenv('VLM_API_KEY') or os.getenv('OPENAI_API_KEY')
 if not key: raise RuntimeError('缺少 VLM_API_KEY 或 OPENAI_API_KEY')
 p=Path(image_path); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 if not p.exists(): raise FileNotFoundError(f'image does not exist: {p}')
 client=OpenAI(api_key=key,base_url=os.getenv('VLM_BASE_URL'),timeout=float(os.getenv('VLM_TIMEOUT_SECONDS','120')),max_retries=1)
 data=base64.b64encode(p.read_bytes()).decode(); started=time.perf_counter()
 resp=client.chat.completions.create(model=os.getenv('VLM_MODEL','gpt-4o-mini'),temperature=0,max_tokens=300,extra_body={'think':False},messages=[{'role':'user','content':[{'type':'text','text':PROMPT},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+data}}]}])
 elapsed=time.perf_counter()-started; raw=resp.choices[0].message.content or ''
 json.dump({'raw':raw},open(out/f'{image_id}_raw.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
 parsed=parse_json(raw); objects=parsed.get('objects',[])
 payload={'image_id':image_id,'method':'VLM','model':os.getenv('VLM_MODEL'),'objects':objects,'counts':{o.get('name','unknown'):o.get('count',1) for o in objects},'runtime_seconds':round(elapsed,4),'error':None}
 json.dump(payload,open(out/f'{image_id}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); return payload

