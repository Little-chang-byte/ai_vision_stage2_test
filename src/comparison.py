import csv,json
from pathlib import Path
from PIL import Image,ImageDraw

def compare_row(image_id,traditional,vlm=None):
 return {"image_id":image_id,"yolo_counts":traditional.get("counts",{}),"yolo_runtime_seconds":traditional.get("runtime_seconds"),"vlm_counts":(vlm or {}).get("counts",{}),"vlm_runtime_seconds":(vlm or {}).get("runtime_seconds"),"vlm_status":("not_run" if vlm is None else "error" if vlm.get("error") else "verified" if vlm.get("runtime_seconds") is not None else "blocked"),"vlm_error":(vlm or {}).get("error"),"vlm_answer_source":(vlm or {}).get("answer_source")}
def save_comparison(rows,output_dir="results/comparison"):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); json.dump(rows,open(out/"comparison.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
 with open(out/"comparison.csv","w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys() if rows else ["image_id"]); w.writeheader(); w.writerows(rows)
 Path(out/"analysis.md").write_text("# 实验对比\n\n仅将实际生成的结果写入本文件。VLM 未运行时标记为 blocked_or_not_run。\n",encoding="utf-8")
