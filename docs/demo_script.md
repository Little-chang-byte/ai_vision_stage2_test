# 真实运行视频录制脚本

录制前确认 Ollama 正在运行，且 `ollama list` 能看到 `qwen3-vl:4b`。

1. 展示项目目录、`data/manifest.csv` 和 `.env.example`（不要展示 `.env` 内容）。
2. 在项目根目录运行：

```powershell
..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --manifest data\manifest.csv
```

3. 展示终端输出，说明处理 D001-D006。
4. 打开 `results/traditional/`，展示 YOLO JSON 和检测框图。
5. 打开 `results/vlm/`，展示一个成功 JSON 和 D005 的 `MAX_OUTPUT_REACHED` 原始记录。
6. 打开 `results/comparison/comparison.json`、`comparison.csv`，说明 `verified` 与 `error` 状态。
7. 说明两种方法都读取 `data/manifest.csv` 的同一原始图片，VLM 不使用 YOLO 结果。

录制时必须保留真实失败状态，不要删除或改写 D005 的失败记录。当前仓库包含脚本但不包含已录制的视频文件；视频需要在本机实际录制后作为最终提交物加入仓库或按考核平台要求上传。
