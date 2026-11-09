# WSL2 Ubuntu + Docker Desktop 本机部署与录屏

这是本机 Linux 容器部署，不是购买或部署远程云服务器。YOLO 使用原 yolo11n.pt 在 CPU 上推理；Qwen3-VL 使用 Windows Ollama。现有 Redis/Celery 随 Compose 保留，但不额外扩大考核范围。

## 环境与启动

1. 启动 Docker Desktop，Settings → Resources → WSL Integration 启用 Ubuntu，Apply & restart。Ubuntu 执行 `docker version` 与 `docker compose version`，必须能看到 Server；仅 Windows 能执行 docker 不等于 Ubuntu 集成完成。
2. Windows Ollama 保持运行，`ollama list` 应包含 `qwen3-vl:4b`。不用更换模型或重复下载已有权重。
3. 在项目目录创建自己的账号配置（只在 .env 不存在时执行）：

```powershell
cd D:\后端_test\stage_3_常歌
$py = 'D:\后端_test\project\.venv-codex-pytorch\Scripts\python.exe'
& $py scripts/configure_local.py
```

账号密码由本人输入，密码仅保存随机盐 PBKDF2 哈希。不要展示 .env，不要将其提交 Git。Compose 会覆盖 TASK_MODE 为 celery、OLLAMA_BASE_URL 为 http://host.docker.internal:11434。

4. Ubuntu 中执行：

```bash
cd /mnt/d/后端_test/stage_3_常歌
docker compose config -q
docker compose build
docker compose up -d --wait
docker compose ps
curl -f http://127.0.0.1:8080/health
docker compose logs --tail=100 api worker nginx
```

Windows 浏览器访问 http://127.0.0.1:8080。只绑定本机回环地址，不开放公网。Dockerfile 安装 Python 3.11、CPU PyTorch 和 requirements.txt 依赖，不在镜像内复制权重。

若当前终端 PATH 尚未包含 Docker，可在 PowerShell 当前进程执行：

```powershell
$env:PATH="$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;"+$env:PATH
docker version
```

本轮遇到 Docker Hub 拉取超时。检查自己的实际代理设置，必要时仅给当前进程配置 HTTP_PROXY/HTTPS_PROXY 后重试；不要照搬其他电脑的端口，不要添加来源不明镜像站。不要将带凭据的代理 URL 写入日志。

## 数据、服务恢复与排错

- 默认 data 挂载到 /app/data，results 挂载到 /app/results，权重只读挂载；重启不清空 SQLite 和图片。
- APP_DATA_DIR、APP_RESULTS_DIR、APP_ENV_FILE 可指定隔离验收目录；APP_PORT 默认 8080。
- `docker compose restart` 后重新登录或刷新历史，核对同一任务 ID、哈希、结果与原图。
- `docker compose stop` 只停止服务；不要使用 `down -v` 清除队列卷，也不要删除数据目录。
- `docker compose logs --tail=100 worker` 检查真实推理与错误；`docker compose exec redis redis-cli ping` 检查队列。
- `docker compose exec worker python -c "import requests; print(requests.get('http://host.docker.internal:11434/api/tags',timeout=10).status_code)"` 检查容器到 Windows Ollama。
- 连接失败时检查 Ollama 监听和 Docker Desktop 网络。如果必须改变 OLLAMA_HOST，先了解监听范围及防火墙，不将无认证 Ollama 暴露公网。
- worker 并发 1，一次任务顺序执行两模型。不自动重跑整个任务；中断记录保留，由操作者确认后标记，再手动新建任务。
- 默认生产数据与自动验收数据是不同目录；不能通过切换数据库路径来声称数据丢失或恢复成功。

## 可重复的真实容器网页验收

先构建 vision-stage3:local；安装 requirements-dev.txt 中 Playwright 并准备 Edge/Playwright ffmpeg。运行：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='D:\后端_test\.browser-runtime'
& $py scripts/docker_web_acceptance.py --ubuntu Ubuntu
```

脚本创建独立 results/docker-web-时间戳 目录和临时账号，仅保存密码哈希。通过真实浏览器登录、上传 D001–D006，实际 Redis/Celery 消费、YOLO 与 Ollama 推理，截屏和录像，重启全部服务并逐项比较数据库返回值。失败原样留在 summary.json。此脚本不会删除原有正式数据。

脚本使用独立 Compose 项目 vision-stage3-acceptance，测试服务占用 8080。正式演示前使用同一个验收 env 文件执行 `docker compose --project-name vision-stage3-acceptance --env-file <验收目录>/.env stop`，然后用本人配置的 .env 启动默认项目。不要向观众提供临时验收账号。

## 真实录屏脚本（需要本人录制桌面启动部分）

使用电脑已有录屏工具，录制真实桌面；不要用截图拼接冒充运行视频。

1. 录制终端：`wsl -l -v`、Ubuntu `uname -a`、`docker version`，说明“WSL2 Ubuntu + Docker Desktop 本机部署，Ollama 在 Windows”。
2. 展示当前 stage3-web、Dockerfile 和 Compose 服务名称，不展开 .env 或密码。
3. 录制 `docker compose up -d --wait`、`docker compose ps`、健康检查。说明依赖已构建进镜像；若演示首次构建，可保留真实等待过程。
4. 打开 http://127.0.0.1:8080，密码输入时暂停录制或使用工具隐私遮挡，登录后继续。
5. 选择一张真实图片，展示预览，点击开始，说明两个模型使用同一 SHA-256。
6. 等待真实结果，展示 YOLO 检测框图、左右模型对象/数量/耗时、数量差异表。失败时展示真实错误，不剪成成功。
7. 刷新页面恢复同一任务；终端重启服务，再查看历史与原图。
8. 展示 worker 日志中的真实任务 ID，与网页对应。结束时说明模型可能误检以及当前本机部署范围。

自动脚本输出的视频仅覆盖浏览器真实操作，不能声称它包含桌面终端启动、本人讲解或远程服务器部署。本人需补录上述部分，个人观点请本人确认。
