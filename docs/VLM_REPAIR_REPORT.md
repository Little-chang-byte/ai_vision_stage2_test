# VLM 修复报告

修复：使用 Ollama 原生 `/api/chat`、`stream=false`、`think=false`、`format=json`；将 `num_predict` 从 300 提升到 500；提示词改为短类别、短证据、只返回可见物体；保留 raw 响应。

修复后专项测试：D002 成功返回 book、power bank、earbuds case、mouse；D003 仍返回空/无效 JSON；D005 需以本次命令实际结果为准。未使用模拟结果。
