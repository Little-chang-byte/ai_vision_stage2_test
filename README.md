# README

## AI 双方案桌面物品清点

本项目使用同一批原始桌面图片，分别运行 YOLO 传统目标检测和 Ollama + Qwen3-VL 4B 视觉语言模型，输出结构化结果并进行比较。六张正式图片为 D001-D006，图片来源和路径记录在 `data/manifest.csv`。

## 环境配置

复制或参考 `.env.example` 创建 `.env`：

```dotenv
VLM_API_KEY=ollama
VLM_BASE_URL=http://127.0.0.1:11434/v1
VLM_MODEL=qwen3-vl:4b
```

`.env` 已被 `.gitignore` 忽略，不应提交到 Git。程序实际调用 Ollama 原生视觉接口 `http://127.0.0.1:11434/api/chat`，读取同一模型名和本地服务配置。

## 安装与运行

```powershell
cd D:\后端_test\ai_vision_stage2
..\project\.venv-codex-pytorch\Scripts\python.exe -m pip install -r requirements.txt
..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --manifest data\manifest.csv
```

只验证 YOLO 时可使用 `--skip-vlm`。单图调试示例：

```powershell
..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --image data\images\e01e756748838fca0a0a73aef3a136f7.jpg --image-id D005
```

## 输出

- `results/traditional/`：YOLO JSON、检测框图和运行记录。
- `results/vlm/`：VLM 结构化结果、原始 Ollama 响应和重试元数据。
- `results/comparison/comparison.json`、`comparison.csv`、`analysis.md`：双方案对比。
- `docs/project_report.md`：项目说明和个人感悟草稿。
- `docs/demo_script.md`：真实运行视频录制脚本。

## 当前验收状态

最近一次完整运行中 YOLO 6/6 成功，Qwen3-VL 5/6 返回合法 JSON；D005 因 `done_reason=length` 记录为 `MAX_OUTPUT_REACHED`。该失败没有被伪造成成功。详细记录见 `FINAL_DELIVERY_REPORT.md`、`docs/VLM_FAILURE_ANALYSIS.md` 和 `docs/VLM_REPAIR_REPORT.md`。
