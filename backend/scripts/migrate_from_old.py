# -*- coding: utf-8 -*-
"""从已有 MySQL 库导入业务数据到本系统（独立可执行，只迁数据不迁图片）。

本脚本【完全自包含】，不依赖项目的 app 包、不读 .env、不需要 FastAPI。
只依赖：pip install sqlalchemy pymysql
可在宿主机任意目录执行。

图片资源请在迁移数据后，自行把已打包好的图片目录复制到目标 data 目录
（本系统把 /profile 映射到 DATA_DIR，图片按原目录结构放好即可）。

只迁移 4 张表：
    cnvp_feeds                    -> sys_feeds
    cnvp_mp_articles              -> sys_mp_articles
    cnvp_mp_classification        -> sys_mp_classification
    cnvp_mp_classification_detail -> sys_mp_classification_detail

=====================================================================
用法（连接串都是标准 SQLAlchemy URL）：
=====================================================================
python migrate_from_old.py \
  --old-url "mysql+pymysql://root:【密码】@源库IP:3308/gzhweb?charset=utf8mb4" \
  --new-url "mysql+pymysql://root:【密码】@目标库IP:3308/zlzchatpython?charset=utf8mb4"

目标库是 SQLite 时，--new-url 换成：
  --new-url "sqlite:///F:/project/python_zlzchat/python/backend/data/zlzchat.db"

可选参数：
    --mode skip|overwrite   主键已存在时 跳过(默认) / 覆盖
    --batch-size N          每批读取行数（默认 500，大数据量可调大）
    --only feeds,articles,classification,detail   只迁移指定表（逗号分隔）

说明：
- 源库只读，目标库写入；两库连接都通过命令行参数显式提供，不依赖任何 .env。
- 按列名原生 SQL 插入，避开 ORM 属性名差异（如 feeds 的 remark 列在新模型叫 version）。
- 自增主键（分类表）保留源库原 ID，维持 classification_id 关联。
- 只迁有效数据：feeds/articles/classification 过滤 is_deleted=0（明细表无该列）。
- 幂等：重复执行不会重复插入（skip 模式按主键跳过 / overwrite 模式覆盖）。
"""
from __future__ import annotations

import argparse
import sys

try:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import Engine
except ImportError:
    print("缺少依赖，请先安装：pip install sqlalchemy pymysql")
    sys.exit(1)

# (目标表, 源表, 插入列, 是否按 is_deleted=0 过滤)
TABLES = {
    "feeds": {
        "new": "sys_feeds",
        "old": "cnvp_feeds",
        "cols": ["feed_id", "wxs_id", "mp_name", "mp_cover", "mp_intro", "status",
                 "sync_time", "show_count", "update_count", "is_deleted",
                 "create_by", "create_time", "update_by", "update_time", "remark"],
        "filter_deleted": True,
    },
    "articles": {
        "new": "sys_mp_articles",
        "old": "cnvp_mp_articles",
        "cols": ["articles_id", "original_id", "wxs_id", "content", "links", "read_type",
                 "content_text", "title", "doc_url", "pic_url", "publish_time", "is_deleted",
                 "create_by", "create_time", "update_by", "update_time"],
        "filter_deleted": True,
    },
    "classification": {
        "new": "sys_mp_classification",
        "old": "cnvp_mp_classification",
        "cols": ["classification_id", "classification_name", "show_count", "icon", "is_deleted",
                 "create_by", "create_time", "update_by", "update_time", "remark"],
        "filter_deleted": True,
    },
    "detail": {
        "new": "sys_mp_classification_detail",
        "old": "cnvp_mp_classification_detail",
        "cols": ["classification_detai_id", "feed_id", "mp_name", "mp_cover", "wxs_id",
                 "classification_id", "create_by", "create_time", "update_by", "update_time", "remark"],
        "filter_deleted": False,  # 源库该表无 is_deleted 列
    },
}

ORDER = ["feeds", "classification", "articles", "detail"]  # 先主表后明细，保持关联
PK_COLS = {
    "feeds": "feed_id",
    "articles": "articles_id",
    "classification": "classification_id",
    "detail": "classification_detai_id",
}


def _table_exists(engine: Engine, table: str) -> bool:
    return table in inspect(engine).get_table_names()


def migrate_table(old_engine: Engine, new_engine: Engine, key: str, mode: str, batch_size: int) -> tuple[int, int]:
    """迁移单表，返回 (成功条数, 跳过条数)。"""
    cfg = TABLES[key]
    old_table, new_table = cfg["old"], cfg["new"]
    cols = cfg["cols"]
    pk = PK_COLS[key]

    if not _table_exists(old_engine, old_table):
        print(f"  [跳过] 源库无表 {old_table}")
        return 0, 0
    if not _table_exists(new_engine, new_table):
        print(f"  [错误] 目标库无表 {new_table}，请先初始化目标库（启动一次服务或跑 init_db.py）")
        return 0, 0

    col_sql = ", ".join(f"`{c}`" for c in cols)
    where = " WHERE is_deleted = 0" if cfg["filter_deleted"] else ""
    # 主键冲突处理语法按目标库方言选择：
    #   MySQL : INSERT IGNORE / REPLACE INTO
    #   SQLite: INSERT OR IGNORE / REPLACE INTO
    dialect = new_engine.dialect.name
    if mode == "overwrite":
        verb = "REPLACE INTO"
    elif dialect == "sqlite":
        verb = "INSERT OR IGNORE INTO"
    else:
        verb = "INSERT IGNORE INTO"
    insert_sql = text(
        f"{verb} `{new_table}` ({col_sql}) VALUES ({', '.join(':' + c for c in cols)})"
    )

    ok_count = skip_count = 0
    last_pk = None
    with old_engine.connect() as src, new_engine.begin() as dst:
        while True:
            if last_pk is None:
                sql = text(
                    f"SELECT {col_sql} FROM `{old_table}`{where} ORDER BY `{pk}` LIMIT :_limit"
                )
                params = {"_limit": batch_size}
            else:
                sql = text(
                    f"SELECT {col_sql} FROM `{old_table}` "
                    f"WHERE `{pk}` > :_last_pk{(' AND is_deleted = 0' if cfg['filter_deleted'] else '')} "
                    f"ORDER BY `{pk}` LIMIT :_limit"
                )
                params = {"_last_pk": last_pk, "_limit": batch_size}

            rows = src.execute(sql, params).mappings().all()
            if not rows:
                break

            for row in rows:
                data = {c: row[c] for c in cols}
                result = dst.execute(insert_sql, data)
                # INSERT IGNORE: rowcount=1 插入成功, 0 被忽略(重复/约束)
                if result.rowcount == 1:
                    ok_count += 1
                else:
                    skip_count += 1
                last_pk = row[pk]

            print(f"  {old_table}: 已处理 {ok_count} 条 (忽略 {skip_count}) ...")
            if len(rows) < batch_size:
                break
    return ok_count, skip_count


def main() -> None:
    parser = argparse.ArgumentParser(description="从已有库导入数据到本系统（独立脚本，只迁数据）")
    parser.add_argument("--old-url", required=True, help="源库连接串")
    parser.add_argument("--new-url", required=True, help="目标库连接串")
    parser.add_argument("--mode", choices=["skip", "overwrite"], default="skip", help="主键冲突处理")
    parser.add_argument("--batch-size", type=int, default=500, help="每批读取行数")
    parser.add_argument("--only", default="", help="只迁移指定表，逗号分隔")
    args = parser.parse_args()

    old_engine = create_engine(args.old_url, pool_pre_ping=True)
    new_engine = create_engine(args.new_url, pool_pre_ping=True)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    selected = [k for k in ORDER if not only or k in only]

    print(f"源库: {args.old_url.split('@')[-1] if '@' in args.old_url else args.old_url}")
    print(f"目标库: {args.new_url.split('@')[-1] if '@' in args.new_url else args.new_url}")
    print(f"迁移模式: {args.mode} | 批次大小: {args.batch_size}")
    print(f"待迁移表: {', '.join(selected)}")
    print("-" * 50)

    total_ok = 0
    for key in selected:
        print(f"[{key}] {TABLES[key]['old']} -> {TABLES[key]['new']}")
        ok, skipped = migrate_table(old_engine, new_engine, key, args.mode, args.batch_size)
        total_ok += ok
        print(f"  完成：{ok} 条" + (f"，跳过 {skipped} 条" if skipped else ""))

    print("-" * 50)
    print(f"[DONE] 数据共迁移 {total_ok} 条记录")
    print("\n提示：图片资源需自行复制到目标 data 目录（本系统把 /profile 映射到 DATA_DIR）。")


if __name__ == "__main__":
    main()
