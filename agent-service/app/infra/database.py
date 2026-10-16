from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

# 获取logger对象
logger = get_logger(__name__)
# 1. 创建引擎
# 1.1-创建异步引擎
engine = create_async_engine(settings.db.url,
                             echo=settings.db.echo,
                             pool_size=settings.db.pool_size,
                             max_overflow=settings.db.max_overflow,
                             pool_recycle=settings.db.pool_recycle
                             )

# 1.2-提供一个初始化连接的方法(激活连接)
async def check_database():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("数据库连接初始化完成~")

# 1.3-提供一个引擎的摧毁方法
async def close_database():
    await engine.dispose()
    logger.info("数据库引擎销毁完成~")

# 2. 创建会话
# 2.1-创建会话工厂
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    # 过期提交: 
    expire_on_commit=False
)

# 2.1-提供获取连接的公共方法
async def get_async_session():
    async with AsyncSessionFactory() as session:
        # session结束后,yield下边代码继续执行
        yield session