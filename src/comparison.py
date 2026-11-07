import csv,json
from pathlib import Path
try:
 from .vlm_pipeline import validate_result_record
 from .traditional_pipeline import validate_yolo_result
except ImportError:
 from vlm_pipeline import validate_result_record
 from traditional_pipeline import validate_yolo_result

def compare_row(image_id,traditional,vlm=None):
 validate_yolo_result(traditional)
 status, error = "not_run", None
 if vlm is not None:
  try:
   validate_result_record(vlm)
   status = "verified"
  except ValueError as exc:
   status, error = "error", vlm.get("error") or str(exc)
 return {"image_id":image_id,"yolo_counts":traditional.get("counts",{}),"yolo_runtime_seconds":traditional.get("runtime_seconds"),"vlm_counts":(vlm or {}).get("counts",{}) if status == "verified" else {},"vlm_runtime_seconds":(vlm or {}).get("runtime_seconds"),"vlm_status":status,"vlm_error":error,"vlm_answer_source":(vlm or {}).get("answer_source")}
def save_comparison(rows,output_dir="results/comparison"):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 with open(out/"comparison.json","w",encoding="utf-8") as json_file:
  json.dump(rows,json_file,ensure_ascii=False,indent=2)
 with open(out/"comparison.csv","w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys() if rows else ["image_id"]); w.writeheader(); w.writerows(rows)
 Path(out/"analysis.md").write_text("# 实验对比\n\n仅将实际生成的结果写入本文件。VLM 未运行时标记为 blocked_or_not_run。\n",encoding="utf-8")
