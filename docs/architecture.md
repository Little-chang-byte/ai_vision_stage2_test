# 第三阶段架构

浏览器原生 HTML/JavaScript → FastAPI → SQLAlchemy/SQLite → Redis/Celery → 第二阶段 YOLO 和 Ollama Qwen3-VL → SQLite → 受 JWT 保护的结果与图片接口。

`TASK_MODE=celery` 是默认模式。API 投递一次双模型工作流，worker 并发 1、预取 1，两模型串行调用。`TASK_MODE=local` 是显式本机实践模式，后台线程使用全局锁串行运行，页面显示此模式。本机六图验收为 local，不能当作 Redis/Celery 实际服务验证。

上传验证 MIME 和实际可解码格式，限 10MB。SHA-256 文件名、请求哈希、任务记录三者绑定。执行前每个模型重新检查文件哈希。原始模型结果先保存，再校验。失败模型的 counts 不进入比较，成功模型保留。

SQLite 通过 create_all 和新增字段 ALTER TABLE 兼容已有记录，不删除旧表。任务备注 PATCH 实践更新，单任务 DELETE 需要 confirm=true 且任务已终止，只删除数据库记录，保留模型文件。历史和任务 API 实践查询，任务提交实践新增。

worker 重复投递通过 pending→running 条件更新保护。模型自动重试只使用原 VLM 有限重试，整个工作流没有自动重跑。进程崩溃可能留下 running，需先确认 worker 已停止，再人工将任务标记中断。任务 UUID 可作为诊断关联键。
