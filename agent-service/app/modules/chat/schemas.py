from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 请求与响应模型

# 请求模型
# 创建会话请求
class CreateChatRequest(BaseModel):
    # 请求参数校验条件
    title: str = Field(default="新会话", min_length=1, max_length=200)

    # 绑定校验字段, 与处理时机
    @field_validator("title", mode="before")
    @classmethod
    def check_title(cls, value: str) -> str:
        # 去除字符串两端的空格
        return value.strip()

# 创建聊天消息请求
class ChatRequest(BaseModel):
    thread_id: UUID
    message: str = Field(min_length=1)


# 响应模型
class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # 根据接口文档确定响应模型
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
