from app.core.exceptions import ApplicationError

# 自定义异常类
# 会话不存在或不属于当前用户
class ChatThreadNotFoundError(ApplicationError):
    """会话不存在或不属于当前用户"""

    status_code = 400
    code = "CHAT_THREAD_NOT_FOUND"
    message = "会话不存在或不属于当前用户"