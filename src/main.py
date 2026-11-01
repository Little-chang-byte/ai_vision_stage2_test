import argparse, json
from dotenv import load_dotenv
from traditional_pipeline import run_yolo
from vlm_pipeline import run_vlm
def main():
    load_dotenv(); ap=argparse.ArgumentParser(); ap.add_argument("--image", required=True); ap.add_argument("--image-id", default="001"); ap.add_argument("--skip-vlm", action="store_true"); args=ap.parse_args()
    print(json.dumps({"traditional":run_yolo(args.image,args.image_id)},ensure_ascii=False,indent=2))
    if not args.skip_vlm: print(json.dumps({"vlm":run_vlm(args.image,args.image_id)},ensure_ascii=False,indent=2))
    else: print("VLM skipped: local YOLO verification only")
if __name__ == "__main__": main()

