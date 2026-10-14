from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(level: str = "INFO") -> None:
    """配置彩色控制台日志，统一 structlog 与标准库 logging 格式。"""

    log_level = _log_level(level)

    # 1. 定义共享的处理器链（提取公共逻辑）
    # 这些处理器负责丰富日志上下文，对 structlog 和标准库 logging 均生效
    shared_processors: list[Any] = [
        # 合并 request_id、conversation_id 等上下文变量
        structlog.contextvars.merge_contextvars,
        # 添加 Logger 名称
        structlog.stdlib.add_logger_name,
        # 添加日志级别
        structlog.stdlib.add_log_level,
        # 添加时间戳
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        # 允许添加占位符参数 (如 log.info("hello %s", "world"))
        structlog.stdlib.PositionalArgumentsFormatter(),
        # 渲染 stack_info=True
        structlog.processors.StackInfoRenderer(),
    ]

    # 2. 配置 Python 标准 logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # 【核心优化】使用 ProcessorFormatter 统一接管标准库日志的格式化
    # 这样第三方库（如 uvicorn, sqlalchemy）的日志也会拥有时间、级别和彩色输出
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            # 处理来自标准库 logging 的日志（ foreign_pre_chain ）
            foreign_pre_chain=shared_processors,
            # 最终渲染器：开启颜色，并设置 pad_event 让日志消息定宽对齐
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    pad_event=35,  # 【视觉优化】固定 event 宽度，让右侧键值对完美对齐
                    sort_keys=True,  # 让附加字段按字母顺序排列，便于查找
                ),
            ],
        )
    )
    root_logger.addHandler(console_handler)

    # 3. 配置 structlog
    structlog.configure(
        processors=[
            *shared_processors,
            # 渲染异常堆栈（放在 wrap_for_formatter 之前）
            structlog.processors.format_exc_info,
            # 【核心优化】将 structlog 日志打包，交由上面的 ProcessorFormatter 统一渲染
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 4. 控制第三方库日志数量（降噪）
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if log_level <= logging.DEBUG else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取 structlog 日志器。"""
    return structlog.get_logger(name)


def _log_level(level: str) -> int:
    """将字符串日志级别转换为 logging 常量。"""
    return getattr(logging, level.strip().upper(), logging.INFO)