# Docker 部署

一个容器同时提供 **API + 前端页面 + 图片资源**。镜像内置前后端，数据通过挂载卷持久化。

## 构建镜像

镜像**内置前后端**：前端 dist 在构建时 COPY 进镜像，运行时无需挂载、无需复制。

**第 1 步（本地）**：前端打包，把生成的 `frontend/dist` 整个目录复制到 NAS 的构建目录，例如 `/volume1/docker/zlzchatpython/frontend/dist/`：
```bash
cd frontend && npm run build     # 生成 frontend/dist（含 index.html、assets/ 等）
```
> 只需复制 `frontend/dist` 这一个目录，不用传 `src/`、`node_modules` 等源码。确保复制后 NAS 上 `frontend/dist/assets/` 存在（之前报错就是这里为空）。

**第 2 步（NAS）**：把 `python/backend/` 和 `Dockerfile` 也放到 NAS 构建目录（`/volume1/docker/zlzchatpython/`），然后构建：

```bash
#打包为amd64
docker buildx build \
  --platform linux/amd64 \
  -t zlzchat:0.0.1 \
  --no-cache \
  --load \
  /volume1/docker/zlzchatpython/

#打包为arm64
docker buildx build \
  --platform linux/arm64 \
  -t zlzchat:0.0.1 \
  --no-cache \
  --load \
  /volume1/docker/zlzchatpython/
```

> 构建时 `frontend/dist` 会被 COPY 进镜像的 `/frontend/dist`，所以运行时不用再挂载前端。`frontend/node_modules` 已在 `.dockerignore` 中排除（不会进镜像）。下方部署命令里的 `zlzchat:latest` 请按实际镜像名替换（这里产出的是 `zlzchat:0.0.1`）。

## 部署方式一：SQLite（最简单，无需外部数据库）

数据库文件放在挂载卷里，容器重建不丢数据。

```bash
docker run -d --name zlzchat \
  -p 8000:8100 \
  --restart unless-stopped \
  -v "$PWD/data:/app/data" \
  -e DATA_DIR=/app/data \
  -e DATABASE_URL="sqlite:////app/data/zlzchat.db" \
  zlzchat:latest
```


- `-p 8000:8100`：宿主机 8000 → 容器 8100，局域网其他设备用 `http://NAS的IP:8000` 访问；若只允许 NAS 本机访问可改成 `-p 127.0.0.1:8000:8100`
- `-v "$PWD/data:/app/data"`：宿主机 `./data` 挂载到容器 `/app/data`，SQLite 库和图片都存这里
- `DATA_DIR=/app/data`：告诉程序图片和数据放这个目录
- `DATABASE_URL="sqlite:////app/data/zlzchat.db"`：用挂载卷里的 SQLite 库（四个斜杠 = 绝对路径）
- 首次启动空库会自动建表 + 默认数据，无需手动初始化

## 部署方式二：MySQL（外部数据库）

MySQL 可以是单独容器或外部服务。

```bash
docker run -d --name zlzchat \
  -p 8000:8100 \
  --restart unless-stopped \
  -v "$PWD/data:/app/data" \
  -e DATA_DIR=/app/data \
  -e DATABASE_URL="mysql+pymysql://root:【密码】@MySQL地址:3308/zlzchatpython?charset=utf8mb4" \
  zlzchat:latest
```

- `DATABASE_URL` 里的 `【密码】`、`MySQL地址:3308`、`root` 分别换成你自己的 MySQL 密码、地址端口、账号（同机可用 `host.docker.internal` 或宿主机 IP；同 docker 网络可用容器名）
- 图片仍存 `/app/data` 挂载卷，数据库走外部 MySQL
- 首次启动会自动建表 + 默认数据（空库检测）

### MySQL 用 docker compose 一起（可选）

```yaml
services:
  zlzchat:
    container_name: zlzchat
    image: zlzchat:0.0.1
    restart: unless-stopped
    ports:
      - "8000:8100"
    environment:
      - DATA_DIR=/app/data
      - DATABASE_URL=mysql+pymysql://root:【密码】@zlzchat-mysql:3306/zlzchatpython?charset=utf8mb4
    volumes:
      - ./data:/app/data
    depends_on:
      - mysql
  mysql:
    image: mysql:8.0
    container_name: zlzchat-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: 【密码】
      MYSQL_DATABASE: zlzchatpython
    volumes:
      - ./mysql-data:/var/lib/mysql
```

> 注意：compose 里 MySQL 端口是容器内部默认 3306， `【密码】` 请换成你自己设置的密码（保持两边一致）。

## 目录与持久化说明

| 容器内路径 | 宿主机挂载 | 内容 |
| --- | --- | --- |
| `/app/data` | `./data` | 图片（uploadGZHCover/uploadGZHFile/uploadCategoryIcon）、SQLite 库、`/profile` 路径映射 |
| `/frontend/dist` | （镜像内） | 前端打包产物（build 时从构建上下文的 `frontend/dist` COPY 进来） |
| `/app` | （镜像内） | 后端代码 |

- 图片访问路径：`/profile/xxx`、`/uploadGZHCover/xxx` 等，全部指向 `DATA_DIR`
- 导入的 `/profile/...` 图片路径直接可用（图片文件拷到 `./data` 即可）
- 前端页面已打进镜像（位于 `/frontend/dist`），运行时无需挂载；更新前端需重建镜像

## 导入已有数据

迁移脚本独立，可单独跑，**只迁数据不迁图片**，详见 `MIGRATE_OLD_DATA.md`。脚本在宿主机执行即可，不用进容器。

SQLite 示例（库文件在宿主机 `./data` 里）：
```bash
python3 scripts/migrate_from_old.py \
  --old-url "mysql+pymysql://root:【密码】@源库IP:3308/gzhweb?charset=utf8mb4" \
  --new-url "sqlite:///$PWD/data/zlzchat.db"
```

MySQL 示例（数据写到外部 MySQL）：
```bash
python3 scripts/migrate_from_old.py \
  --old-url "mysql+pymysql://root:【密码】@源库IP:3308/gzhweb?charset=utf8mb4" \
  --new-url "mysql+pymysql://root:【密码】@MySQL地址:3308/zlzchatpython?charset=utf8mb4"
```

要点：
- 迁移完成后重启容器：`docker restart zlzchat`，数据即可见。
- **图片需自行复制**：把图片目录按原结构复制到宿主机挂载的 `./data`（容器内 `/app/data`），`/profile/xxx` 路径即可直接访问。详见 `MIGRATE_OLD_DATA.md` 的"图片目录怎么放"。

## 常用命令

```bash
docker ps                      # 查看运行
docker logs -f zlzchat         # 看日志
docker restart zlzchat         # 重启
docker stop zlzchat && docker rm zlzchat   # 停止并删除
```

访问：<http://NAS的IP:8000>（API 文档 <http://NAS的IP:8000/docs>；NAS 本机可用 127.0.0.1）
