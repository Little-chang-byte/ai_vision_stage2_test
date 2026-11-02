# AI 双方案桌面物品清点

同一张图片分别使用 YOLO 目标检测和视觉大模型识别物品，并保存结构化结果。YOLO 可独立运行；VLM 需要真实 API Key。

## 运行

```powershell
cd ai_vision_stage2
..\project\.venv-codex-pytorch\Scripts\python.exe -m pip install -r requirements.txt
..\project\.venv-codex-pytorch\Scripts\python.exe src/main.py --image data/images/test.jpg --image-id 001 --skip-vlm
```

配置 `.env` 后执行不带 `--skip-vlm` 的命令即可进行真实多模态调用。结果位于 `results/traditional/` 和 `results/vlm/`。
## 批量运行

```powershell
..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --manifest data\manifest.csv --skip-vlm
```

输出：`results/traditional/`、`results/comparison/comparison.json`、`results/comparison/comparison.csv`。

## 查找目标

查找入口目前可通过 Python 调用 `src.search.search_yolo`，例如查询“公交车”。它使用真实 YOLO 边界框，不把 VLM 描述当作坐标。

当前 manifest 中的素材用于管线验证；正式提交前必须替换为有授权的桌面物品图片。
