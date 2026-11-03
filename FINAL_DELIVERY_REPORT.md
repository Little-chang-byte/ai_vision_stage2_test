# 最终交付报告（持续更新）

已完成：项目结构、YOLO/VLM 真实推理代码、统一入口、环境变量示例、基础文档。
待确认：YOLO 权重下载、真实推理、VLM API、并排结果、批量测试和 Git 历史。
阻断：需要 `VLM_API_KEY` 或 `OPENAI_API_KEY` 才能执行真实多模态推理。
## 当前已验证结果

- 批量入口：`src/main.py --manifest data/manifest.csv --skip-vlm` 已真实运行 3 张图片。
- YOLO 结果已写入 `results/traditional/`；比较文件已写入 `results/comparison/comparison.json` 和 `comparison.csv`。
- 查找 MVP 已真实运行：查询“公交车”映射到 `bus`，找到 1 个目标并生成边界框、位置和置信度。
- `data/images/bus.jpg`、`zidane.jpg` 是 Ultralytics 随包素材，用于管线验证，不应作为最终桌面场景证据。
- VLM 仍未验证，原因是没有 API Key。
## Qwen3-VL 当前结果

已改用 Ollama 原生 `/api/chat`，因为 OpenAI-compatible 返回的 content 在部分图片上为空。当前 6 张图片中 3 张成功返回 JSON，3 张返回空或无效 JSON，已标记为 error，未伪造结果。原始响应保存在 `results/vlm/`。
