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
## 2026-11-03 Qwen3-VL 修复验证
- 通过 Ollama 原生 `/api/chat` 接口发送原始图片，设置 `stream=false`、`think=false`、`format=json`。
- 单张 D001 真实返回结构化 JSON 成功。
- 完整 manifest 6 张：D001、D004、D006 成功；D002、D003、D005 返回空/无效 JSON，标记为 error，保留 raw 响应。
- comparison 状态已修复为 verified/error/not_run/blocked 语义。

## 2026-11-04 最终接管复验

- 使用命令 `..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --manifest data\manifest.csv` 完整运行 D001-D006。
- YOLO 6/6 完成；Ollama `qwen3-vl:4b` 请求 6/6 发出。
- VLM 合法 JSON：D001、D002、D003、D004、D006；D005 为 `MAX_OUTPUT_REACHED`，`done_reason=length`。
- 所有 VLM 原始响应和重试元数据保存在 `results/vlm/`；比较文件已重新生成。
- 两种管线均从 manifest 读取同一原始图片路径；未使用模拟结果。
