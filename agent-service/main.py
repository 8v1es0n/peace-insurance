from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.core.logging import configure_logging, get_logger
import uvicorn

# 初始化日志系统
configure_logging(settings.logging.level)
# 通过名字创建日志对象
logger = get_logger(__name__)

# 生命周期管理函数
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 项目启动时执行
    from app.infra.database import check_database, close_database
    # 1. 初始化连接
    await check_database()
    # 2. 初始化checkpointer连接池
    from app.infra.checkpointer import init_checkpointer, close_checkpointer
    checkpointer = await init_checkpointer()
    from app.agents.insurance_advisor import init_insurance_agent
    agent = init_insurance_agent(checkpointer)
    app.state.agent = agent
    yield

    # 项目关闭时执行
    # 销毁checkpointer
    await close_checkpointer()
    # 销毁引擎
    await close_database()


# 创建FastAPI实例对象
app = FastAPI(
    title=settings.app.name,
    debug=settings.app.debug,
    lifespan=lifespan
)

@app.exception_handler(ApplicationError)
async def handle_application_error(
    request: Request,
    exc: ApplicationError, # 捕获到的异常（这里用自定义异常基类捕获，所有业务异常都会匹配到）
) -> JSONResponse:
    logger.warning(f"业务处理异常，请求路径:{request.url},请求方式:{request.method},异常信息:{exc}")
    return JSONResponse(
        status_code=exc.status_code, # 异常中自带status
        content={
            "code": exc.code,        # 异常中自带code
            "message": exc.message,  # 异常中自带message
        },
    )

from app.modules.product.router import router as product_router
from app.modules.chat.router import router as chat_router

# 创建 app 后注册路由
app.include_router(product_router)
app.include_router(chat_router)


# 创建健康检查接口
@app.get("/health", summary="健康检测接口")
async def health_check():
    logger.info("执行健康检查")
    return {"status": "健康检查通过"}

# 基于Uvicorn启动服务
if __name__ == "__main__":
    import sys
    uvicorn.run(
        app,
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
        # 指定事件循环器
        loop= "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"
    )