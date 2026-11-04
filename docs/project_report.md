# AI 视觉第二阶段项目说明

## 1. 项目目标

本项目对同一批桌面照片分别运行 YOLO 传统目标检测和 Ollama 本地 Qwen3-VL 4B 视觉语言模型，保存结构化结果并进行对比。两种方法都直接读取 `data/manifest.csv` 中的同一原始图片；VLM 不使用 YOLO 框或 YOLO 输出作为输入。

## 2. 当前实现

- 统一入口：`src/main.py`
- YOLO 管线：`src/traditional_pipeline.py`，输出检测框、类别、置信度、运行时间和结果图。
- VLM 管线：`src/vlm_pipeline.py`，调用 Ollama 原生 `/api/chat`，使用 `.env` 中的模型配置，保存原始响应、`done_reason`、重试记录和结构化 JSON。
- 对比管线：`src/comparison.py`，生成 `results/comparison/comparison.json`、`comparison.csv` 和 `analysis.md`。
- 查找 MVP：`src/search.py`，根据 YOLO 框实现静态图片目标查找。

## 3. 环境与数据

- 操作系统：Windows
- Python：`project.venv-codex-pytorch`
- VLM 服务：Ollama `http://127.0.0.1:11434/api/chat`
- VLM 模型：`qwen3-vl:4b`
- 数据：6 张个人拍摄桌面图片，ID 为 D001-D006；旧的 Ultralytics 示例图保存在 `data/legacy/images/`，未从仓库删除。

## 4. 最新真实运行结果（2026-11-04）

执行命令：

```powershell
..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --manifest data\manifest.csv
```

- YOLO：6/6 张完成真实推理。
- Ollama/Qwen3-VL：6/6 张请求成功发出，5/6 张返回可解析 JSON。
- D001、D002、D003、D004、D006：`vlm_status=verified`，响应 `done_reason=stop`。
- D005：`vlm_status=error`，`error=MAX_OUTPUT_REACHED`，`done_reason=length`；该失败被保留，没有使用替代或模拟结果。
- VLM 成功率：5/6（83.3%）。本项目把“返回合法 JSON”作为成功标准，不把 reasoning/thinking 当作识别结果。

结果文件：

- `results/traditional/`
- `results/vlm/`
- `results/comparison/comparison.json`
- `results/comparison/comparison.csv`
- `results/comparison/analysis.md`

## 5. 结果解读与限制

YOLO 与 VLM 的类别和数量存在差异，这是实际对比结果，不是人工真值。`data/manifest.csv` 的 notes 仅记录拍摄场景，不构成已经核实的标注。项目当前没有声称六张图片的识别结果全部准确。

D005 的失败属于模型输出达到长度上限，程序已记录失败原因和每次重试的元数据。其余图片的成功只表示接口返回了合法结构化结果，仍需人工查看图片和 JSON 评估语义准确性。

## 6. 个人感悟（提交前请按本人实际经历补充）

本项目让我认识到，传统检测模型和视觉语言模型的输出能力不同：YOLO 更适合稳定地产生类别、置信度和边界框；VLM 更容易给出自然语言层面的物品判断，但结构化输出会受提示词、输出长度和场景复杂度影响。排查空响应时，我先保留原始响应，再检查 `message.content`、thinking 字段和 `done_reason`，最后切换到 Ollama 原生接口并增加短提示重试。D005 仍然失败说明输出上限和复杂小目标场景需要继续优化。

以上感悟段落是基于本次仓库日志的交付草稿；提交前应补充本人实际录制、调试和演示过程中的具体细节。
