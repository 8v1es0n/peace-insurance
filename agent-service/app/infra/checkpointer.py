from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 0.创建checkpointer专用连接池
checkpoint_pool = AsyncConnectionPool(
    conninfo=settings.db.checkpointer_url,
    min_size=1,  # 池最小连接数
    max_size=5,  # 池最大连接数
    kwargs={
        "autocommit": True,  # 自动提交事务
        "prepare_threshold": 0,  # 不做预准备sql
        "row_factory": dict_row,  # 查询结果以dict返回
    },
    open=False,  # 不自动创建连接
)


async def init_checkpointer() -> AsyncPostgresSaver:
    """初始化checkpointer"""

    # 1.初始化连接池
    await checkpoint_pool.open()  # 初始化连接
    await checkpoint_pool.wait()  # 等待连接池就绪

    # 2.创建checkpointer
    checkpointer = AsyncPostgresSaver(checkpoint_pool)
    await checkpointer.setup()
    logger.info("Checkpointer初始化成功~")
    return checkpointer

async def close_checkpointer() -> None:
    """关闭Checkpointer连接池"""
    await checkpoint_pool.close()
    logger.info("Checkpointer连接池已关闭~")