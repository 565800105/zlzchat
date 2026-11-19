"""轻量任务状态存储：供前端刷新后查询后台同步任务的真实结果。

任务在后端同步执行（前端刷新不影响其继续运行），前端发起时生成 taskId，
后端开始/结束时写入状态，前端刷新后凭 taskId 查询。
"""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
# task_id -> {status, msg, updateNum, startTime, endTime}
_tasks: dict[str, dict[str, Any]] = {}
_MAX = 200
_TTL = 24 * 3600  # 保留 24 小时


def start_task(task_id: str) -> None:
    with _lock:
        _tasks[task_id] = {
            "status": "running",
            "msg": "正在执行中",
            "updateNum": 0,
            "startTime": int(time.time() * 1000),
            "endTime": None,
        }
        _trim()


def finish_task(task_id: str, *, status: str, msg: str = "", update_num: int = 0) -> None:
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            task = {"startTime": int(time.time() * 1000)}
            _tasks[task_id] = task
        task["status"] = status
        task["msg"] = msg or ("执行完成" if status == "success" else "执行失败")
        task["updateNum"] = update_num
        task["endTime"] = int(time.time() * 1000)
        _trim()


def get_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        task = _tasks.get(task_id)
        return dict(task) if task else None


def _trim() -> None:
    """清理过期与超额记录。调用时已持有锁。"""
    now = time.time()
    expired = [
        k for k, v in _tasks.items()
        if v.get("endTime") and (now - v["endTime"] / 1000) > _TTL
    ]
    for k in expired:
        _tasks.pop(k, None)
    while len(_tasks) > _MAX:
        oldest = next(iter(_tasks))
        _tasks.pop(oldest, None)
