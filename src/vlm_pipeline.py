import base64,json,os,time,requests
from pathlib import Path
PROMPT='List visible objects. Return JSON only with an objects array. Do not guess objects not visible.'
def parse_json(raw):
 raw=(raw or '').strip(); dec=json.JSONDecoder()
 for i,c in enumerate(raw):
  if c=='{':
   try:return dec.raw_decode(raw[i:])[0]
   except json.JSONDecodeError: pass
 raise ValueError('VLM_EMPTY_OR_INVALID_JSON')
def run_vlm(image_path,image_id,output_dir='results/vlm'):
 p=Path(image_path); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 data=base64.b64encode(p.read_bytes()).decode(); started=time.perf_counter()
 r=requests.post('http://127.0.0.1:11434/api/chat',json={'model':os.getenv('VLM_MODEL','qwen3-vl:4b'),'messages':[{'role':'user','content':PROMPT,'images':[data]}],'stream':False,'think':False,'format':'json','options':{'temperature':0,'num_predict':300}},timeout=float(os.getenv('VLM_TIMEOUT_SECONDS','120')))
 r.raise_for_status(); body=r.json(); raw=body.get('message',{}).get('content',''); json.dump(body,open(out/f'{image_id}_raw.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
 parsed=parse_json(raw); objs=parsed.get('objects',[]); objs=[{'name':x,'count':1,'evidence':'visible in image'} if isinstance(x,str) else x for x in objs]; elapsed=time.perf_counter()-started
 payload={'image_id':image_id,'method':'VLM','model':body.get('model'),'objects':objs,'counts':{o.get('name','unknown'):o.get('count',1) for o in objs},'runtime_seconds':round(elapsed,4),'error':None}
 json.dump(payload,open(out/f'{image_id}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); return payload
