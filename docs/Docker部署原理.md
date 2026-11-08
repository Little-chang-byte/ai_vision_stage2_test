# Docker 部署原理

Dockerfile 基于 Python 3.11 slim 安装 requirements 并运行 FastAPI。Compose 组合 nginx、api、worker、redis；Redis 队列只开放内部网络，worker prefork 并发 1。Nginx 映射 8080，代理 API 和页面，上传限 10MB。原模型权重通过只读宿主机挂载提供，不打进镜像。

SQLite、上传文件与模型结果使用 data/results 挂载持久化；Redis 使用命名卷。API 和 worker 共享相同数据库路径和模型目录。容器用 host.docker.internal 访问宿主机 Ollama，Linux host-gateway 配置只解决地址解析，仍需监听、防火墙与连通实测。

当前没有 Docker CLI 和可用 Linux 子系统，因此构建、Compose、Nginx 和重启持久化均待验证。不得把配置存在当作部署成功。
