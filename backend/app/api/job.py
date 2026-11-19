"""定时任务配置接口 /api/admin/job。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.base import to_dict, to_dicts
from app.models.classification import CnvpMpClassification
from app.models.feeds import CnvpFeeds
from app.models.sys_job import SysJob
from app.models.user import SysUser
from app.response import ApiException, ok, page_result
from app.services.crud import get_val, apply_audit, fill, paginate, parse_ids
from app.services.log_service import write_log
from app.services.scheduler import add_job, remove_job, run_once

router = APIRouter(prefix="/admin/job", tags=["定时任务"])

_FIELDS = [
    "job_name", "cron_expression", "misfire_policy",
    "concurrent", "status", "acount_type", "classification_id", "wxs_id", "remark",
]


@router.get("/list")
def list_jobs(
    pageNum: int = 1,
    pageSize: int = 10,
    jobName: str | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    stmt = select(SysJob)
    if jobName:
        stmt = stmt.where(SysJob.job_name.like(f"%{jobName}%"))
    stmt = stmt.order_by(SysJob.job_id.desc())
    rows, total = paginate(db, stmt, pageNum, pageSize)
    return page_result(to_dicts(rows), total, pageNum, pageSize)


@router.get("/classification-options")
def classification_options(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    rows = db.query(CnvpMpClassification).filter(CnvpMpClassification.is_deleted == 0).all()
    return ok([{"value": r.classification_id, "label": r.classification_name} for r in rows])


@router.get("/feed-options")
def feed_options(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    rows = db.query(CnvpFeeds).filter(CnvpFeeds.is_deleted == 0).all()
    return ok([{"value": r.wxs_id, "label": r.mp_name} for r in rows])


@router.post("/add")
def add_job_api(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not get_val(payload, "job_name") or not get_val(payload, "cron_expression"):
        raise ApiException("任务名称与 cron 表达式不能为空")
    row = SysJob(
        job_name="",
        cron_expression="",
        misfire_policy="3",
        concurrent="1",
        status="0",
        acount_type="2",
    )
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, True)
    db.add(row)
    db.commit()
    add_job(row)
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="新增定时任务", user_name=user.user_name, request_params=payload)
    return ok(msg="新增成功")


@router.post("/edit")
def edit_job_api(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = db.get(SysJob, get_val(payload, "job_id")) if get_val(payload, "job_id") else None
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, False)
    db.commit()
    add_job(row)  # 重新加载调度（含暂停判断）
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="编辑定时任务", user_name=user.user_name, request_params=payload)
    return ok(msg="修改成功")


@router.post("/remove")
def remove_jobs(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    ids = [int(x) for x in parse_ids(get_val(payload, "ids")) if str(x).isdigit()]
    if not ids:
        raise ApiException("未选择记录")
    for job_id in ids:
        remove_job(job_id)
    db.query(SysJob).filter(SysJob.job_id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="删除定时任务", user_name=user.user_name, request_params=payload)
    return ok(msg="删除成功")


@router.post("/run/{job_id}")
def run_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """立即执行一次。"""
    job = db.get(SysJob, job_id)
    if not job:
        raise ApiException("任务不存在", 404)
    run_once(job_id)
    # 立即执行属于任务执行，归类为 job，便于在日志页按"任务"筛选查看
    write_log(
        log_type="job", method="POST", url=str(request.url.path),
        description=f"立即执行任务: {job.job_name}", user_name=user.user_name,
        request_params={"jobId": job_id},
    )
    # 明细日志：记录"定时任务请求发起"这一节点（异步执行随后由 update_all 记录批次）
    from app.services.task_detail_log_service import new_batch, write_detail

    write_detail(
        batch_id=new_batch(),
        task_type="job",
        job_id=job_id,
        job_name=job.job_name,
        step="task_start",
        message=f"定时任务请求发起（手动立即执行）：{job.job_name}，操作人 {user.user_name}",
    )
    return ok(msg="已触发执行")


@router.post("/toggle/{job_id}")
def toggle_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    row = db.get(SysJob, job_id)
    if not row:
        raise ApiException("任务不存在", 404)
    row.status = "1" if row.status == "0" else "0"
    db.commit()
    add_job(row)
    return ok({"status": row.status}, msg="状态已切换")


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    row = db.get(SysJob, job_id)
    if not row:
        raise ApiException("记录不存在", 404)
    return ok(to_dict(row))
