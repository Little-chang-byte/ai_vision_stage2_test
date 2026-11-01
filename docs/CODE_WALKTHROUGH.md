# 代码说明
- `traditional_pipeline.py` 加载 YOLO，提取类别、置信度、边界框并保存 JSON/图片。
- `vlm_pipeline.py` 用同一原图调用真实视觉模型并保存原始响应。
- `main.py` 是统一入口；`--skip-vlm` 仅用于本地 YOLO 验证。
- YOLO 阈值在 `run_yolo(..., conf=0.25)`；提示词在 `vlm_pipeline.py` 的 `PROMPT`。
