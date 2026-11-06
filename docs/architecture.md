# 第三阶段架构

FastAPI 提供上传、认证、任务和历史接口，并直接托管演示页面。SQLAlchemy 将任务、图片哈希、两种模型状态、耗时结果和错误写入 SQLite。后台任务调用第二阶段的 YOLO 检测器和 Ollama Qwen3-VL 调用入口，两个模型接收同一个上传文件。页面轮询任务状态并并排展示真实返回值。

当前实现使用 FastAPI `BackgroundTasks` 完成单机异步执行，后续可将 `run_task` 接入 Redis/RQ worker。Docker、Nginx 和 Linux 部署属于后续工程化阶段。
