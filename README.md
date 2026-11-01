# AI 双方案桌面物品清点

同一张图片分别使用 YOLO 目标检测和视觉大模型识别物品，并保存结构化结果。YOLO 可独立运行；VLM 需要真实 API Key。

## 运行

```powershell
cd ai_vision_stage2
..\project\.venv-codex-pytorch\Scripts\python.exe -m pip install -r requirements.txt
..\project\.venv-codex-pytorch\Scripts\python.exe src/main.py --image data/images/test.jpg --image-id 001 --skip-vlm
```

配置 `.env` 后执行不带 `--skip-vlm` 的命令即可进行真实多模态调用。结果位于 `results/traditional/` 和 `results/vlm/`。
