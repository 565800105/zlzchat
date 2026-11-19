"""清理项目中的 __pycache__ 目录和 .pyc 文件。

放在 python/ 根目录，执行时会递归清理整个项目（backend + frontend 无关文件除外）。

用法：
    python clean_pycache.py              # 实际删除
    python clean_pycache.py --dry-run    # 只预览会删除什么，不真正删
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 __pycache__ 和 .pyc")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不删除")
    args = parser.parse_args()

    dirs: list[Path] = []
    files: list[Path] = []

    for path in ROOT.rglob("*"):
        # 跳过 node_modules 等无关大目录，加快速度
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        if path.is_dir() and path.name == "__pycache__":
            dirs.append(path)
        elif path.is_file() and path.suffix == ".pyc":
            files.append(path)

    print(f"找到 __pycache__ 目录 {len(dirs)} 个，.pyc 文件 {len(files)} 个")

    if args.dry_run:
        for d in dirs:
            print(f"  [目录] {d.relative_to(ROOT)}")
        for f in files:
            print(f"  [文件] {f.relative_to(ROOT)}")
        print("\n（dry-run 模式，未实际删除）")
        return

    for d in dirs:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    for f in files:
        f.unlink(missing_ok=True)

    print(f"[DONE] 已删除 {len(dirs)} 个 __pycache__ 目录，{len(files)} 个 .pyc 文件")


if __name__ == "__main__":
    main()
