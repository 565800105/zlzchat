# ZLZCHAT 公众号信息管理系统（Python + Vue3 版）

基于 **Python FastAPI** 实现后端、**Vue3 + Arco Design Vue** 实现前端。提供后台鉴权、微信文章定时拉取、飞书/钉钉通知、日志审计、对外开放 API 等能力。数据表统一使用 `sys_` 前缀（共 12 张）。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy 2.0 / APScheduler / httpx |
| 数据库 | SQLite（默认，零配置）或 MySQL（通过 `DATABASE_URL` 切换） |
| 鉴权 | JWT + bcrypt + 登录日志 |
| 前端 | Vue3 / Vite / Arco Design Vue / Pinia / Vue Router / Axios |

## 目录结构

```
python/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口（CORS/日志中间件/路由/静态资源/前端托管）
│   │   ├── config.py        # 全局配置（.env 覆盖，含 DATA_DIR）
│   │   ├── database.py      # 数据库引擎与会话
│   │   ├── db_init.py       # 数据库初始化逻辑（启动时自动调用）
│   │   ├── models/          # ORM 模型（sys_* 前缀）
│   │   ├── api/             # 路由（auth/accounts/feeds/articles/classification/updateLog/config/job/logs/open）
│   │   ├── services/        # 业务服务（crud/wxread/notify/scheduler/log/config）
│   │   └── utils/           # 安全工具（JWT/bcrypt）
│   ├── scripts/
│   │   ├── init_db.py       # 手动初始化数据库（启动已自动初始化，一般无需手动跑）
│   │   └── migrate_from_old.py  # 从旧库导入数据+图片（独立可执行）
│   ├── data/                # 默认数据目录（图片、SQLite 库），可由 DATA_DIR 覆盖
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # Vue3 前端
├── Dockerfile               # 多阶段构建（前端 Node + 后端 Python）
├── DEPLOY.md                # Docker 部署说明（SQLite / MySQL）
├── OPEN_API.md              # 对外开放 API 文档
├── MIGRATE_OLD_DATA.md      # 旧库数据导入说明（脚本在 backend/scripts/）
└── clean_pycache.py         # 清理 __pycache__ / .pyc
```

## 快速启动

### 1. 后端

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

首次启动会**自动检测空库并初始化**（建表 + 默认管理员 + 默认配置 + 默认任务），无需手动执行 `init_db.py`。也可以手动跑 `python scripts/init_db.py`（幂等，重复执行安全）。

默认管理员：`admin` / `admin123`（登录后可在个人中心修改密码）。
接口文档：<http://127.0.0.1:8100/docs>

> 图片/数据库等数据默认放 `backend/data`，可通过环境变量 `DATA_DIR` 覆盖（Docker 挂载卷必用）。详见 [DEPLOY.md](DEPLOY.md)。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 Vite 输出的地址（默认 <http://127.0.0.1:5173>），开发代理已配置 `/api` → `http://127.0.0.1:8100`。

### 3. 数据库切换为 MySQL（可选）

复制 `backend/.env.example` 为 `backend/.env`，设置：

```
DATABASE_URL=mysql+pymysql://root:密码@localhost:3308/zlzchatpython?charset=utf8mb4
```

并安装驱动 `pip install pymysql`。启动服务时会自动建表初始化。

> **数据导入**：本项目表名统一使用 `sys_*` 前缀。如需导入已有数据，用独立脚本 `scripts/migrate_from_old.py`，详见 [MIGRATE_OLD_DATA.md](MIGRATE_OLD_DATA.md)。源库 `remark` 列在 `sys_feeds` 模型映射为属性 `version`（列名仍是 `remark`）。

## 核心配置说明（后台「配置项」页面）

| 配置键 | 名称 | 默认 | 说明 |
|---|---|---|---|
| `api.checkFeedUpdate` | 检测公众号是否更新 | 1 | 1检测版本 2不检测 |
| `api.updateFeedTime` | 更新间隔(秒) | 60 | 每条更新的基础等待，勿小于30 |
| `api.apiKey` | 请求 key | 空 | 开放 API 鉴权 key，未设置时调用开放接口会提示先设置 |
| `api.articlecont` | 是否全文抓取 | 1 | 1抓取正文 2不抓取 |
| `api.publicUrl` | 服务器对外域名/IP | 空 | 订阅源(Atom/RSS)中图片等资源地址的拼接前缀 |
| `api.serverUrl` | 外部中转服务地址 | http://111.229.83.152 | 扫码/刷新登录态等外部服务地址 |
| `api.feishuSecret` / `api.feishuUrl` | 飞书秘钥/Webhook | 空 | 飞书机器人通知 |
| `api.dingdingSecret` / `api.dingdingToken` | 钉钉秘钥/Token | 空 | 钉钉机器人通知 |
| `api.middlewareKey` | 中转服务通讯 key | 内置值 | 只读，用于解析账号 cookie，配置页不可改 |
| `rss.name` / `rss.count` | 订阅源名称/条数 | 我的订阅/50 | Atom/RSS 输出 |

### 微信读书账号扫码登录

账号配置页点击「扫码添加账号」即可登录，无需手填 Cookie/JWT：

1. 后端 `GET /api/admin/accounts/qrcode` 调用外部服务 `{API_SERVER_URL}/getEwm` 获取二维码。
2. 前端展示二维码并每 2 秒轮询 `GET /api/admin/accounts/qrcode/check?uid=&installId=`。
3. 扫码成功后后端调用外部 `{API_SERVER_URL}/ewmCallback`，用返回的 `nickName`/`token` **自动创建 category=1 的微信账号**，并调用 `refSkeyAPPNoTime` 刷新登录态。

> 扫码依赖外部服务可达：需在 `backend/.env` 配置 `API_SERVER_URL`，并在「配置项」页填好 `api.token`。若外部服务不通，扫码接口会返回明确的配置错误提示。当前仅保留微信读书一种登录类型。

外部文章拉取服务地址在 `backend/.env` 的 `API_SERVER_URL`。

## 主要功能页面

| 路由 | 功能 |
|---|---|
| `/admin/cms/classification` | 订阅源分类（含分类明细抽屉） |
| `/admin/cms/updateLog` | 更新记录 |
| `/admin/cms/feeds` | 公众号信息（同步最新/历史/清空） |
| `/admin/cms/mparticles` | 文章信息（查看/重抓正文） |
| `/admin/cms/accounts` | 账号配置 |
| `/admin/cms/config` | 配置项管理 |
| `/admin/monitor/job` | 定时任务配置（选择分组/公众号、账号策略、立即执行） |
| `/admin/monitor/logs` | 日志查看（只看最新、按类型/异常筛选） |

## 部署与迁移

- **Docker 部署**（SQLite / MySQL 两种方案、挂载卷、环境变量）：见 [DEPLOY.md](DEPLOY.md)
- **导入已有数据**（独立脚本，只迁数据，支持 MySQL/SQLite 目标库、Docker；图片需自行复制）：见 [MIGRATE_OLD_DATA.md](MIGRATE_OLD_DATA.md)
- **对外开放 API**（接口清单、鉴权、调用示例）：见 [OPEN_API.md](OPEN_API.md)
- 清理字节码缓存：`python clean_pycache.py`（加 `--dry-run` 预览）

## 设计说明

- **鉴权**：JWT + bcrypt，管理员账号体系独立。
- **定时任务**：APScheduler，cron 支持 6/7 位表达式（秒 分 时 日 月 周 [年]）；支持账号策略（异常切换/轮询）、选择分组（分组ID→明细展开为 wxs_id）、选择公众号；执行前防重入、禁止并发。
- **文章拉取**：账号 skey 刷新、book/readinfo 版本检测、book/articles 拉取、正文抓取、封面下载、去重入库、断点续传、同步状态复位。
- **通知**：飞书/钉钉机器人（钉钉毫秒时间戳、飞书秒时间戳且 key/data 相反）。
- **日志**：每次 HTTP 请求与定时任务执行均落库到 `sys_request_log`，后台只保留最新 `LOG_KEEP_RECENT`（默认100）条，异常原因直观可见；登录与操作日志独立记录。
- **开放 API**：`/api/open/*` 提供 feedList/文章列表/详情/Atom/触发同步/订阅源增删等功能，用 `api.apiKey` 鉴权。详见 [OPEN_API.md](OPEN_API.md)。
- **数据表**：统一 `sys_*` 前缀，针对大数据量建立了查询索引；已有数据可用独立脚本导入（见上）。
