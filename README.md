# 视觉实验室 · 第三阶段

复用第二阶段 YOLO11n 与 Ollama qwen3-vl:4b，对同一张上传图片并排显示真实检测框、类别、数量和运行时间。FastAPI 提供 API 与网页，SQLAlchemy/SQLite 保存任务，JWT 保护图片和记录，Celery/Redis 提供独立 worker 路径。

## 本机启动

以下虚拟环境、单元测试和本机 local 模式已在 Windows 验证。

```powershell
cd D:\后端_test\stage_3_常歌
$py = 'D:\后端_test\project\.venv-codex-pytorch\Scripts\python.exe'
& $py scripts/configure_local.py
& $py -m uvicorn src.web_app:app --host 127.0.0.1 --port 8000
```

配置脚本交互读取账号和密码，仅创建缺失的 .env，既有文件请手动迁移。实际浏览器访问 http://127.0.0.1:8000，输入你配置的账号密码。页面支持上传、清除、重新执行、历史与刷新恢复、备注和确认删除。退出登录清除浏览器会话 Token。JWT 为 8 小时，单用户演示用途。

已有环境安装新增依赖用 `& $py -m pip install -r requirements-dev.txt`。安装依赖已执行。新建环境可使用 `python -m venv .venv`，然后 `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`，此全新环境重建命令尚未实测。

Ollama 必须提前运行并具有 qwen3-vl:4b。YOLO 权重为仓库原 yolo11n.pt，不支持 SAM。模型识别可能出错，数量展示原模型实际输出。

## 环境变量

- JWT_SECRET 与 DEMO_PASSWORD_HASH 必须配置。无公开默认密码。
- DEMO_USER 默认 teacher，可自行配置。
- OLLAMA_BASE_URL 默认 http://127.0.0.1:11434，原生 /api/chat。
- VLM_NUM_PREDICT 默认 4000；VLM_TIMEOUT_SECONDS 默认 120。
- TASK_MODE 默认 celery，local 为显式本机串行模式。
- REDIS_URL 默认 redis://127.0.0.1:6379/0。
- DATABASE_URL 默认 data/stage3.db，UPLOAD_DIR 和 RESULT_DIR 可隔离测试数据。

## 队列实践

默认 celery 模式需要真实 Redis。本机已有 WSL2 Ubuntu 和 Docker Desktop；优先使用 Compose 同时启动 Redis、API、worker 和 Nginx。Windows 独立 Redis/solo 组合仅保留为参考。

```powershell
# 先启动 Redis，确认 PING/PONG
$env:TASK_MODE='celery'
& $py -m celery -A src.queue_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
# 另一个终端，同样配置 TASK_MODE=celery 后启动 API
& $py -m uvicorn src.web_app:app --host 127.0.0.1 --port 8000
```

Windows solo 模式只用于学习。Linux 使用 prefork 并发 1 执行软/硬时限。整个工作流不自动重试，VLM 内部仍最多 2 次重试。中断恢复说明见部署指南。

## API

/health、/docs；POST /api/auth/login；受保护的 POST /api/upload、POST /api/compare、GET /api/tasks/{id}、GET /api/history、GET /api/tasks/{id}/image/{original|yolo}、PATCH /api/tasks/{id}、DELETE /api/tasks/{id}?confirm=true。

## 测试与证据

```powershell
& $py -m unittest discover -s tests -v
$env:PLAYWRIGHT_BROWSERS_PATH='D:\后端_test\.browser-runtime'
& $py scripts/real_web_regression.py --budget 4000
```

真实回归脚本用本机 Edge、临时凭据和独立 SQLite 启动 local 模式服务，经浏览器真实上传、推理和刷新恢复，产生截图、原始响应、任务 JSON 与真实 WebM 录像。它不证明 Redis/Celery 消费。证据路径见 docs/最终考核验收报告.md。

本轮 WSL2 + Docker Desktop 的操作步骤、录屏脚本见 [WSL2本机部署与录屏](docs/WSL2本机部署与录屏.md)，实际结果见 [本轮容器验收](docs/本轮容器验收.md)。远程云服务器不属于本轮范围。代码目录为 src、frontend、scripts、tests、deploy、docs。data/uploads 和 data/stage3.db 为运行数据，results 为原始模型和验收证据，均不会提交到 Git。
