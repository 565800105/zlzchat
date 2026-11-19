"""数据库初始化脚本（手动执行）。

用法：python scripts/init_db.py
说明：服务启动时若检测为空库也会自动初始化，此脚本供手动重建/初始化使用。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_init import init_database

if __name__ == "__main__":
    init_database(verbose=True)
