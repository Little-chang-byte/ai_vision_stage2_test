import csv,json,os
from dotenv import load_dotenv
from traditional_pipeline import YoloDetector
from vlm_pipeline import run_vlm
from comparison import compare_row,save_comparison
def main():
 load_dotenv(); ap=__import__('argparse').ArgumentParser(); ap.add_argument('--image'); ap.add_argument('--manifest'); ap.add_argument('--image-id',default='001'); ap.add_argument('--skip-vlm',action='store_true'); args=ap.parse_args(); detector=YoloDetector(); rows=[]
 items=[(args.image,args.image_id)] if args.image else [(r['path'],r['image_id']) for r in csv.DictReader(open(args.manifest,encoding='utf-8-sig'))]
 for path,image_id in items:
  y=detector.detect(path,image_id); v=None
  if not args.skip_vlm:
   try: v=run_vlm(path,image_id)
   except Exception as e: v={'error':str(e),'image_id':image_id,'method':'VLM'}
  rows.append(compare_row(image_id,y,v))
 save_comparison(rows); print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
