# 20 分钟人工验收
1. 激活 `project/.venv-codex-pytorch`，运行 README 命令。
2. 打开 `results/traditional/001.json` 和图片，核对真实 YOLO 输出。
3. 将 `conf=0.25` 改为 `0.5`，重新运行并比较检测数量。
4. 配置 VLM Key 后运行不带 `--skip-vlm` 的命令。
5. 修改 `PROMPT`，重新运行同一图片，比较 VLM JSON。
