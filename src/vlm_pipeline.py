import base64,json,os,time,requests
from pathlib import Path
PROMPT='List visible physical objects. Return JSON only: {"objects":[{"name":"short English category","count":1,"uncertain":false}]}. Do not describe text or explain reasoning.'
RETRY='Return JSON only:\n{"objects":[]}\nList up to 6 clearly visible physical objects. Use short English category names. Do not describe book text. Do not explain your reasoning.'
def parse_json(raw):
 dec=json.JSONDecoder(); raw=(raw or '').strip()
 for i,c in enumerate(raw):
  if c=='{':
   try:return dec.raw_decode(raw[i:])[0]
   except json.JSONDecodeError: pass
 raise ValueError('VLM_EMPTY_OR_INVALID_JSON')
def request(prompt,data):
 r=requests.post('http://127.0.0.1:11434/api/chat',json={'model':os.getenv('VLM_MODEL','qwen3-vl:4b'),'messages':[{'role':'user','content':prompt,'images':[data]}],'stream':False,'think':False,'format':'json','options':{'temperature':0,'num_predict':500}},timeout=float(os.getenv('VLM_TIMEOUT_SECONDS','120'))); r.raise_for_status(); return r.json()
def run_vlm(image_path,image_id,output_dir='results/vlm'):
 p=Path(image_path); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); data=base64.b64encode(p.read_bytes()).decode(); started=time.perf_counter(); attempts=[]
 for n,prompt in enumerate([PROMPT,RETRY],1):
  body=request(prompt,data); msg=body.get('message',{}); raw=msg.get('content','') or ''; done=body.get('done_reason') or body.get('done_reason','stop'); attempts.append({'attempt':n,'done_reason':done,'raw_content_length':len(raw),'thinking_length':len(msg.get('thinking','') or '')})
  try: parsed=parse_json(raw); break
  except ValueError:
   parsed=None
 if parsed is None:
  payload={'image_id':image_id,'method':'VLM','model':body.get('model'),'objects':[],'counts':{},'runtime_seconds':round(time.perf_counter()-started,4),'done_reason':attempts[-1]['done_reason'],'raw_content_length':attempts[-1]['raw_content_length'],'error':'MAX_OUTPUT_REACHED' if attempts[-1]['done_reason']=='length' else 'VLM_EMPTY_OR_INVALID_JSON','attempts':attempts}
  json.dump(body,open(out/f'{image_id}_raw.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); json.dump(payload,open(out/f'{image_id}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); return payload
 objs=[]
 for x in parsed.get('objects',[]):
  if isinstance(x,str): objs.append({'name':x,'count':1,'uncertain':False})
  else: objs.append({'name':x.get('name','unknown'),'count':x.get('count',1),'uncertain':bool(x.get('uncertain',False))})
 payload={'image_id':image_id,'method':'VLM','model':body.get('model'),'objects':objs,'counts':{o['name']:o['count'] for o in objs},'runtime_seconds':round(time.perf_counter()-started,4),'done_reason':attempts[-1]['done_reason'],'raw_content_length':attempts[-1]['raw_content_length'],'error':None,'attempts':attempts}
 json.dump(body,open(out/f'{image_id}_raw.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); json.dump(payload,open(out/f'{image_id}.json','w',encoding='utf-8'),ensure_ascii=False,indent=2); return payload
