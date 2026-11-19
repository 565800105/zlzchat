"""定时任务调度器：用 APScheduler 替代 Java Quartz。

职责：cron 动态增删改、暂停/恢复、立即执行、启动恢复；允许任务并发执行；
执行时创建 sys_update_log 记录并调用微信文章拉取服务。保留原任务的
账号策略、选择分组、选择公众号等参数语义。
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.sys_job import SysJob
from app.models.update_log import CnvpUpdateLog
from app.services.log_service import write_log
from app.services.wxread import WxReadService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
JOB_PREFIX = "zlzchat_job_"


def parse_quartz_cron(expr: str) -> CronTrigger:
    """把 Quartz 6/7 位 cron（秒 分 时 日 月 周 [年]）转成 APScheduler CronTrigger。

    Quartz 中 '?' 表示不指定，映射到 None；day 与 day_of_week 二选一。
    """
    parts = expr.split()
    if len(parts) < 5:
        raise ValueError(f"cron 表达式字段不足: {expr}")
    # 补齐到 6 位（秒 分 时 日 月 周）
    parts = (parts + ["*", "*", "*", "*", "*", "*"])[:6]
    second, minute, hour, day, month, week = parts

    def norm(value: str) -> str:
        return "*" if value in ("?", "*") else value

    day_of_week = None
    day_value: str | None = norm(day)
    if week not in ("?", "*"):
        day_of_week = norm(week)
        day_value = None  # day 与 day_of_week 互斥，优先 week

    return CronTrigger(
        second=norm(second),
        minute=norm(minute),
        hour=norm(hour),
        day=day_value,
        month=norm(month),
        day_of_week=day_of_week,
    )


def execute_job(job_id: int) -> None:
    """单个任务执行入口（update_log、异常捕获、请求日志）。

    不做执行前防重入检查：同一任务允许并发执行。
    """
    started = time.time()
    error_msg = ""
    with SessionLocal() as db:
        job = db.get(SysJob, job_id)
        if not job:
            return

        log = CnvpUpdateLog(
            log_sta="1", log_result_sta="0", log_catagory="1", update_num=0,
        )
        db.add(log)
        db.commit()

        result = WxReadService(db).update_all(job, log.log_id)
        error_msg = "" if result.get("code") == 200 else result.get("msg", "")
        write_log(
            log_type="job",
            description=f"定时任务: {job.job_name}",
            user_name="system",
            status_code=result.get("code", 500),
            success=result.get("code") == 200,
            error_msg=error_msg or None,
            cost_time=int((time.time() - started) * 1000),
        )


_DEFAULT_JOB_NAME = "定时拉取微信文章"


def ensure_default_job_enabled() -> None:
    """确保内置种子任务处于开启状态（不写入任何配置项）。"""
    with SessionLocal() as db:
        job = db.query(SysJob).filter(SysJob.job_name == _DEFAULT_JOB_NAME).first()
        if job and job.status != "0":
            job.status = "0"
            db.commit()
            logger.info("已将默认定时任务设为开启: %s", _DEFAULT_JOB_NAME)
        # 清理历史遗留的内部标记，避免出现在配置项管理页
        from app.models.sys_config import SysConfig

        stale = db.query(SysConfig).filter(SysConfig.config_key == "sys.defaultJobEnabled").first()
        if stale:
            db.delete(stale)
            db.commit()


def add_job(job: SysJob) -> None:
    """把一个 SysJob 加入调度器（已存在则先移除）。"""
    job_id = f"{JOB_PREFIX}{job.job_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    if job.status == "1":  # 暂停
        return
    try:
        trigger = parse_quartz_cron(job.cron_expression)
        scheduler.add_job(
            execute_job,
            trigger=trigger,
            args=[job.job_id],
            id=job_id,
            name=job.job_name,
            replace_existing=True,
            misfire_grace_time=60,
            coalesce=True,
            max_instances=20,  # 允许同一任务并发执行
        )
    except Exception as exc:
        logger.error("添加任务 %s 到调度器失败: %s", job.job_name, exc)


def remove_job(job_id: int) -> None:
    scheduler_id = f"{JOB_PREFIX}{job_id}"
    if scheduler.get_job(scheduler_id):
        scheduler.remove_job(scheduler_id)


def run_once(job_id: int) -> None:
    """立即异步执行一次任务（不阻塞请求）。"""
    threading.Thread(target=execute_job, args=(job_id,), daemon=True).start()


def start() -> None:
    """启动调度器并从数据库恢复所有启用任务。"""
    if scheduler.running:
        return
    with SessionLocal() as db:
        jobs = db.query(SysJob).all()
        for job in jobs:
            add_job(job)
    scheduler.start()
    logger.info("定时任务调度器已启动，已加载 %d 个任务", len(jobs))


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("定时任务调度器已关闭")
