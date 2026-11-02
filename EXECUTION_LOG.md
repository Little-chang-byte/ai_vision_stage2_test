# Execution log

## 2026-11-02
- 检查工作区：现有 `project/` 为第一阶段 CIFAR-10 项目，无根目录 Git 仓库。
- Python 3.14.6；CPU PyTorch 2.15.0；已安装 OpenCV、Ultralytics、FastAPI、OpenAI SDK 和 dotenv。
- 新建独立目录 `ai_vision_stage2/`，保留原项目。
- 已加入 YOLO 与 VLM 真实推理代码和最小运行入口。
- 待执行：YOLO 权重下载与真实推理、VLM API 调用、对比结果和 Git 提交。
- 阻断：VLM 需要 `VLM_API_KEY` 或 `OPENAI_API_KEY`，不得用模拟结果替代。
## 2026-11-02 实际运行
- 使用 `data/images/test.jpg` 运行 YOLO11n 真实推理成功。
- 输出：`results/traditional/001.json` 与 `results/traditional/001.jpg`。
- 实际识别：person 1、tie 1；运行耗时约 3.9403 秒。
- VLM 尚未运行：当前未发现 API Key，未生成模拟结果。
# 2026-11-02 P0 progress
- Added `data/manifest.csv` with three locally available image assets. Two are Ultralytics bundled street images; they are pipeline fixtures, not desktop-scene evidence, and must be replaced with licensed desktop photos before final submission.
- Refactored YOLO into reusable `YoloDetector`, added path validation and model reuse.
- Added batch manifest entry point and comparison JSON/CSV/analysis files.
- Added static YOLO search MVP with Chinese aliases and real bounding-box visualization.
- VLM remains unverified because no API key is present; no simulated result was generated.
