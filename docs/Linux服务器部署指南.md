# Linux 与 Docker 部署实践指南

2026-11-09 本机 WSL2 Ubuntu + Docker Desktop 已完成容器网页六图验收。现有环境无需重复安装，具体步骤见《WSL2本机部署与录屏.md》。云服务器未提供；下面涉及远程 SSH、服务器系统安装的命令仍未验证，不能作为远程部署证据。官方 Windows Redis 安装路径为 WSL、Docker 或 Memurai，参考 https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-on-windows/ 。

## 未来远程服务器准备（本轮不要求；已安装的本机步骤不必重复）

1. 管理员 PowerShell 启用 WSL2，运行 `wsl --install -d Ubuntu`，按提示重启并完成 Ubuntu 用户初始化。系统命令位置为 C:/Windows/System32/wsl.exe。
2. 安装 Docker Desktop，启用 WSL2 后端，在 Docker Desktop 显示 Engine running 后运行 `docker version` 与 `docker compose version`。这些操作可能要求管理员权限、重启或许可确认。
3. 如已有授权的 Ubuntu 22.04/24.04 服务器，提供 IP、SSH 用户名和密钥。不要将私钥放入仓库。
4. 本地用 `ssh-keygen -t ed25519` 生成密钥，按服务器控制台指引安装公钥，用 `ssh -i <私钥路径> <用户>@<IP>` 登录。远程登录尚未执行。

## Linux 环境准备

按 Docker 官方安装文档安装 Engine 与 Compose 插件，再检查 `docker version`、`docker compose version`。参考 https://docs.docker.com/engine/install/ubuntu/ 。先阅读官方步骤再执行系统级安装，使用自己的 sudo 授权。

```bash
mkdir -p ~/projects
cd ~/projects
git clone -b stage3-web https://github.com/Little-chang-byte/ai_vision_stage2_test.git
cd ai_vision_stage2_test
pwd
ls -lah
mkdir -p data/uploads results
chmod 700 data/uploads
```

确认远程 stage3-web 已存在后才能 clone。原 YOLO 权重已在仓库，先 `ls -lh yolo11n.pt`，缺失时才用 scp 从本机上传，避免重复复制。Docker 镜像排除了权重，由 Compose 只读挂载。

Ollama 按官方 Linux 指引安装 https://docs.ollama.com/linux ，然后 `ollama pull qwen3-vl:4b`。先用 `curl http://127.0.0.1:11434/api/tags` 确认模型。若要让容器连接宿主机 Ollama，需要在可信 Docker 接口可达地址监听。可配置 `OLLAMA_HOST=0.0.0.0:11434`，同时用主机防火墙阻止公网访问 11434，仅允许本机和 Docker 网络。开放监听属于用户需要审查的主机安全操作。

## 配置和启动

复制 .env.example 到 .env。将 DEMO_PASSWORD_HASH 替换为交互生成值，JWT_SECRET 使用 Python secrets 生成，避免写入 shell 历史。可以在配置好依赖的项目环境运行 scripts/configure_local.py 生成缺失的 .env，再改 TASK_MODE=celery。不要覆盖已有 .env。Compose 已固定 REDIS_URL 为服务内网 redis，数据库为 /app/data/stage3.db，Ollama 地址为 host.docker.internal。

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 api worker redis nginx
curl http://127.0.0.1:8080/health
```

浏览器经 8080 登录上传，确认 worker 日志出现任务消费，数据库最终状态和页面结果对应同一任务 ID。然后重启 `docker compose restart`，再次查询历史和图片。尚未执行这些验收。

## 进程、权限、日志与备份

使用 `ps aux`、`ss -lntp` 查看进程与监听。`docker compose logs -f worker` 查看模型执行，Ctrl+C 退出日志不会停止容器。使用 `docker compose stop` 和 `docker compose start` 停启。仅 Nginx 8080 映射宿主机，Redis 与 API 保持内网。防火墙只放行实际需要的 SSH 和网页端口，切勿在 SSH 远程会话中盲目更改规则。

停止 API 和 worker 后备份 `data/stage3.db`、`data/uploads`、`results`。可用 `tar -czf backup-$(date +%F).tgz data results`，备份位置应在仓库外。更新前确认 `git status -sb`，再 `git pull --ff-only origin stage3-web`、构建和启动。不得使用 reset 覆盖现有修改。

## worker 策略与中断

同一工作流串行 YOLO→VLM，concurrency=1、prefetch=1，任务开始前条件更新防止重复执行。VLM 内部最多重试 2 次，单请求默认 120 秒。整个任务没有自动重试，避免故障后重复消耗模型资源。Linux prefork 软时限 840 秒、硬时限 900 秒。Windows solo 不保证 Celery 硬终止能力，只用于学习。

worker 被 kill、超时或机器断电后，SQLite 可能留下 running。先停止并确认所有相关 worker 退出，再由管理员执行：

```bash
python -c "from src.queue_app import mark_interrupted; mark_interrupted.run('<任务ID>')"
```

这只标记中断并保留已有成功结果与文件。需要再试时从网页重新提交成新任务，不自动重跑。队列发布失败记录 QUEUE_UNAVAILABLE 和任务 ID。

## 故障排查

- 401 检查登录、JWT 用户与过期时间。
- 503 检查 Redis、worker、JWT_SECRET 和密码哈希配置。
- 图片 415 检查真实文件能否解码。
- 哈希失败检查文件是否被修改，重新上传。
- VLM length 查看每次 attempt 原始响应，采用统一预算，不按图片编号分支。
- 容器连接 Ollama 失败检查 host-gateway、监听地址与主机防火墙。
- Linux Docker、SSH、GPU 容器能力均待真实环境验证。
