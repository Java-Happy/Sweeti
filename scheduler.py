import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("crypto_radar.scheduler")

scheduler = AsyncIOScheduler(timezone="UTC")


async def collect_market_job():
    """自动采集市值排名前250的币种，并记录任务日志。"""
    from main import get_market_data
    from storage import (
        save_market_snapshot,
        start_collection_run,
        finish_collection_run
    )

    run_id = None
    started = time.perf_counter()
    fetched_count = 0
    saved_count = 0

    try:
        run_id = start_collection_run(
            source="coingecko",
            currency="usd"
        )

        logger.info("开始自动采集 CoinGecko 行情，任务ID：%s", run_id)

        data = await get_market_data("usd", 250, 1)

        if not data:
            raise ValueError("CoinGecko 本次没有返回行情数据")

        fetched_count = len(data)

        result = save_market_snapshot(data, currency="usd")
        saved_count = result["saved_count"]

        duration = round(time.perf_counter() - started, 2)

        finish_collection_run(
            run_id=run_id,
            status="success",
            fetched_count=fetched_count,
            saved_count=saved_count,
            duration_seconds=duration
        )

        logger.info(
            "自动采集完成：获取 %s 个，保存 %s 个，耗时 %s 秒，任务ID：%s",
            fetched_count,
            saved_count,
            duration,
            run_id
        )

    except Exception as exc:
        duration = round(time.perf_counter() - started, 2)

        if run_id is not None:
            try:
                finish_collection_run(
                    run_id=run_id,
                    status="failed",
                    fetched_count=fetched_count,
                    saved_count=saved_count,
                    duration_seconds=duration,
                    error_message=str(exc)
                )
            except Exception:
                logger.exception("写入采集失败日志时发生错误")

        logger.exception("自动行情采集失败，任务ID：%s", run_id)


def start_scheduler():
    if scheduler.running:
        logger.info("调度器已经运行")
        return

    scheduler.add_job(
        collect_market_job,
        trigger="interval",
        minutes=5,
        id="market_collection",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60
    )

    scheduler.start()

    job = scheduler.get_job("market_collection")

    logger.info("自动行情调度器已启动")
    logger.info("采集间隔：5分钟")
    logger.info("任务ID：%s", job.id)
    logger.info("下次执行时间：%s", job.next_run_time)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("自动行情调度器已停止")
