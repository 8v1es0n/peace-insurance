# 路由层
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_async_session

from .schemas import ChatResponse, CreateChatRequest
from .service import ChatService



# 1.创建APIRouter对象
router = APIRouter(prefix="/api/v1/chat-threads", tags=["会话管理"])

# 获取service的会话对象
def get_service(session:AsyncSession = Depends(get_async_session)):
    return ChatService(session)


# 创建聊天会话
@router.post("", summary="创建会话", response_model=ChatResponse)
async def create_chat(
        request: CreateChatRequest,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service),
) -> ChatResponse:

    return await service.create_chat(user_id, request.title)


# 查询会话列表
@router.get("", summary="查询会话列表", response_model=list[ChatResponse])
async def get_chats(
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service)
):
    return await service.get_chats(user_id)


# 修改会话名
@router.patch("/{thread_id}", summary="修改会话名", response_model=ChatResponse)
async def update_chat_title(
        request: CreateChatRequest,
        thread_id: UUID,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service),
):
    return await service.rename(thread_id, user_id, request.title)


# 删除会话
@router.delete("/{thread_id}", summary="删除会话", response_model=ChatResponse)
async def delete_chat(
        thread_id: UUID,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service)
):
    await service.delete_chat(thread_id, user_id)
    # 向前端返回成功信息
    return Response(status_code=status.HTTP_204_NO_CONTENT)