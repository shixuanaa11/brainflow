"""独立 Job Worker 进程：outbox 投递 + stale job recovery（可与 API 同机并行）"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.job_service import get_job_service
from core.logs import get_logger
from src.graph import init_graph

log = get_logger("job_worker")


async def main() -> None:
    """不启动 HTTP；仅注册工具、recovery、outbox 循环"""
    await init_graph()
    svc = get_job_service()
    # 不调度新 job 执行（由 API 进程 schedule）；只负责投递与 recovery 重入队
    await svc.start(run_outbox_loop=True)
    log.info("job worker started (outbox + recovery)")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await svc.stop()


if __name__ == "__main__":
    asyncio.run(main())
