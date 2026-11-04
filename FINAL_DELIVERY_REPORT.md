# 最终交付报告

## 交付范围

本仓库包含可运行代码、六张个人拍摄图片的正式 manifest、YOLO 与 Ollama/Qwen3-VL 真实运行结果、对比文件、项目说明和视频录制脚本。`.env` 未提交，`.env.example` 保留。

## 验收运行

时间：2026-11-04

命令：

```powershell
..\project\.venv-codex-pytorch\Scripts\python.exe src\main.py --manifest data\manifest.csv
```

实际结果：

| 项目 | 结果 |
|---|---:|
| 正式图片 | 6 张（D001-D006） |
| YOLO 真实完成 | 6/6 |
| Ollama 请求发出 | 6/6 |
| VLM 合法 JSON | 5/6 |
| VLM 失败 | D005：`MAX_OUTPUT_REACHED` |
| VLM 模型 | `qwen3-vl:4b` |
| VLM 接口 | `http://127.0.0.1:11434/api/chat` |
| 同一原始图片 | 是，manifest 路径由两条管线共同读取 |

D001、D002、D003、D004、D006 的结果文件包含 `done_reason=stop` 和结构化对象；D005 的原始响应、三次尝试和 `done_reason=length` 均保存在 `results/vlm/D005_raw.json` 与 `results/vlm/D005.json`。没有使用 reasoning/thinking 冒充结果，也没有填充模拟识别结果。

## 交付文件

- 源码：`src/`
- 配置模板：`.env.example`、`.gitignore`
- 正式数据清单：`data/manifest.csv`、`data/formal_manifest.csv`
- YOLO 结果：`results/traditional/`
- VLM 原始与结构化结果：`results/vlm/`
- 对比结果：`results/comparison/comparison.json`、`comparison.csv`、`analysis.md`
- 项目说明与个人感悟草稿：`docs/project_report.md`
- 录制脚本：`docs/demo_script.md`

## 对 PDF 要求的完成情况

已完成：同图双方案、传统模型运行、视觉大模型真实接入、结果保存、对比文件、项目文档、Git 历史和失败记录。

待人工完成：录制并提交真实运行视频；视频不能由仓库文件替代。当前环境没有可直接录制桌面视频的工具，因此本次未伪造视频文件，录制步骤见 `docs/demo_script.md`。

## 当前限制

D005 的复杂场景仍可能触发模型输出长度上限。它被作为真实失败案例保留。类别差异属于实验观察，manifest notes 不是人工核实的 ground truth；如考核要求精度指标，应另行制作并人工确认标注。
