# Linux 服务器部署指南

当前没有云服务器，因此本文是可执行的部署准备，未标记为远程部署完成。

1. 使用 SSH 登录 Linux 主机，安装 Docker Engine 和 Docker Compose 插件。
2. `git clone` 获取仓库并切换 `stage3-web`。
3. 复制 `.env.example` 为 `.env`，设置 `JWT_SECRET`、演示账号和 Ollama 地址。
4. 上传 `yolo11n.pt`，确认 Ollama 主机可以访问 `qwen3-vl:4b`。
5. 执行 `docker compose build` 和 `docker compose up -d`。
6. 使用 `docker compose ps`、`docker compose logs -f api` 检查服务。
7. 通过 80 端口访问 Nginx，使用 `/health` 检查 API。
8. 更新时执行 `git pull`、`docker compose build`、`docker compose up -d`。

数据库和上传文件挂载在 `data`，结果挂载在 `results`。生产环境应限制 8000、6379 等内部端口的公网访问，并将 JWT_SECRET 设置为至少 32 字节随机值。
