# 数据导入：从已有库导入数据

脚本 `scripts/migrate_from_old.py` 是**完全独立可执行**的，**只迁移数据，不迁移图片**：
- 不依赖项目的 `app` 包、不读 `.env`、不需要 FastAPI
- 只依赖 `sqlalchemy` + `pymysql`
- 可在宿主机任意目录执行

源库只读，目标库写入，不改动源系统。

> **图片需自行复制**：本系统把 `/profile` 映射到数据目录 `DATA_DIR`。迁移数据后，把已打包好的图片目录（如 `uploadGZHCover/`、`uploadGZHFile/` 等）按原目录结构复制到 `DATA_DIR` 即可，`/profile/xxx` 路径会直接访问到，**无需改写数据库**。

## 迁移的表

| 源库表 | 目标库表 | 说明 |
| --- | --- | --- |
| `cnvp_feeds` | `sys_feeds` | 公众号信息（过滤 is_deleted=0） |
| `cnvp_mp_articles` | `sys_mp_articles` | 文章信息（过滤 is_deleted=0） |
| `cnvp_mp_classification` | `sys_mp_classification` | 订阅源分类（保留原分类ID） |
| `cnvp_mp_classification_detail` | `sys_mp_classification_detail` | 分类明细（保留原关联） |

> 其他表（账号、用户、配置、任务、日志等）不迁移，目标库由服务启动时自动初始化。

## 前置条件

1. 目标库已初始化（启动一次新服务即可自动建表，或手动 `python scripts/init_db.py`）。
2. 执行脚本的 Python 环境装好依赖：`pip install sqlalchemy pymysql`
3. 准备好源库、目标库的连接信息（地址、端口、库名、账号密码）。

> **必须用 Python 3 运行**（脚本用了 Python 3 语法）。若 `python` 指向 Python 2 会报
> `SyntaxError: Non-ASCII character`——请改用 `python3 migrate_from_old.py`，或先激活 Python 3 的虚拟环境。
> 可用 `python3 --version` 确认（需 3.8+）。

## 用法

连接串都是标准 SQLAlchemy URL 格式：
```
# MySQL 目标库
mysql+pymysql://账号:密码@地址:端口/库名?charset=utf8mb4
# SQLite 目标库（相对路径）
sqlite:///data/zlzchat.db
# SQLite 目标库（Windows 绝对路径）
sqlite:///F:/project/xxx/data/zlzchat.db
```

> 源库始终是源系统的 MySQL；目标库可以是 MySQL 或 SQLite，脚本会自动按目标库方言选择插入语法（MySQL 用 `INSERT IGNORE`，SQLite 用 `INSERT OR IGNORE`）。

### 命令行参数（最直观）

```bash
python3 migrate_from_old.py \
  --old-url "mysql+pymysql://root:【密码】@源库IP:3308/gzhweb?charset=utf8mb4" \
  --new-url "mysql+pymysql://root:【密码】@目标库IP:3308/zlzchatpython?charset=utf8mb4"
```

**目标库是 SQLite 时**（把 `--new-url` 换成 sqlite 连接串即可）：

```bash
python3 migrate_from_old.py \
  --old-url "mysql+pymysql://root:【密码】@源库IP:3308/gzhweb?charset=utf8mb4" \
  --new-url "sqlite:///F:/project/python_zlzchat/python/backend/data/zlzchat.db"
```

> 源库名：源系统 `application-dev.yml` 是 `gzhweb`，`application-pro.yml`（生产）是 `grwxgzh`，按实际填写。

## 可选参数

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `--old-url` | 连接串 | 源库（必填） |
| `--new-url` | 连接串 | 目标库（必填） |
| `--mode` | `skip`（默认）/ `overwrite` | 主键已存在时：跳过 / 覆盖 |
| `--batch-size` | 整数，默认 500 | 每批读取行数，数据量大可调 1000~2000 |
| `--only` | 逗号分隔表名 | 只迁指定表，如 `--only feeds,articles` |

## Docker 场景

迁移脚本在**宿主机执行**（不用进容器）：

```bash
python3 migrate_from_old.py \
  --old-url "mysql+pymysql://root:【密码】@源库IP:3308/gzhweb?charset=utf8mb4" \
  --new-url "sqlite:///$PWD/data/zlzchat.db"
```

- 若目标库是 MySQL 且容器端口映射到宿主机，`--new-url` 里写 `localhost:映射端口`。
- 迁移完成后 `docker restart <容器名>` 即可看到数据。
- 图片：把图片目录复制到宿主机挂载给容器的 `./data` 目录即可（见下）。

### 图片目录怎么放

本系统把 `/profile` 映射到数据目录 `DATA_DIR`（默认 `backend/data`，Docker 里是挂载卷 `/app/data`）。图片按原目录结构放好即可：

- 公众号封面：`DATA_DIR/uploadGZHCover/`
- 文章图片：`DATA_DIR/uploadGZHFile/{wxsId}/{originalId}/`
- 分类图标：`DATA_DIR/uploadCategoryIcon/`

数据库里存的 `/profile/uploadGZHCover/xxx.png` 会直接对应到 `DATA_DIR/uploadGZHCover/xxx.png`，无需改写数据库。

Docker 部署时，把图片复制到宿主机上挂载给容器的那个 `./data` 目录（容器内即 `/app/data`），容器挂载后即可见。

## 注意事项

- **幂等**：默认 `skip` 模式重复执行不会重复插入（按主键跳过），可放心重跑。
- **主键**：公众号/文章保留源库 UUID 主键；分类表保留源库 bigint ID，维持 `classification_id` 关联。
- **有效数据**：只迁 `is_deleted=0` 的数据（明细表无该字段，全迁）。
- **分批读取**：大数据量不会一次性载入内存，按 `batch-size` 分批迁移。
- **执行顺序**：公众号 → 分类 → 文章 → 分类明细，保证关联完整性。

## 常见问题

**Q：报 `Unknown database` 或连接拒绝？**
A：连接串的地址/端口/库名不对。源系统 MySQL 端口通常是 3308。

**Q：报 `Table 'xxx.cnvp_feeds' doesn't exist`？**
A：源库名填错了，或该库没有这些表。用 `application-pro.yml` 的库名（grwxgzh）再试。

**Q：报目标库无表 `sys_xxx`？**
A：目标库没初始化。先启动一次新服务（会自动建表），或先跑 `scripts/init_db.py`。

**Q：迁移后图片 404？**
A：图片不在迁移脚本范围内，需自行按原目录结构把图片复制到 `DATA_DIR`（Docker 里是宿主机挂载的 `./data`），确认 `/profile/xxx` 对应的文件真实存在。
