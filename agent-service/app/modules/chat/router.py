# 路由层
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic_settings.sources.providers import aws
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_async_session
from starlette.requests import Request

from .schemas import ChatResponse, CreateChatRequest, ChatRequest
from .service import ChatService



# 1.创建APIRouter对象
router = APIRouter(prefix="/api/v1", tags=["会话与聊天管理"])

# 获取service的会话对象
def get_service(request: Request, session:AsyncSession = Depends(get_async_session)):
    return ChatService(session, request.app.state.agent)


"""会话管理"""
# 创建聊天会话
@router.post("/chat-threads", summary="创建会话", response_model=ChatResponse)
async def create_chat(
        request: CreateChatRequest,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service),
) -> ChatResponse:

    return await service.create_chat(user_id, request.title)


# 查询会话列表
@router.get("/chat-threads", summary="查询会话列表", response_model=list[ChatResponse])
async def get_chats(
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service)
):
    return await service.get_chats(user_id)


# 修改会话名
@router.patch("/chat-threads/{thread_id}", summary="修改会话名", response_model=ChatResponse)
async def update_chat_title(
        request: CreateChatRequest,
        thread_id: UUID,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service),
):
    return await service.rename(thread_id, user_id, request.title)


# 删除会话
@router.delete("/chat-threads/{thread_id}", summary="删除会话", response_model=ChatResponse)
async def delete_chat(
        thread_id: UUID,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_service)
):
    await service.delete_chat(thread_id, user_id)
    # 向前端返回成功信息
    return Response(status_code=status.HTTP_204_NO_CONTENT)


"""聊天管理"""
@router.post("/chat", summary="与AI聊天")
async def chat_stream(
    chat_request: ChatRequest,
    user_id: Annotated[int, Header(alias="x-user-id")],
    service: ChatService = Depends(get_service)
):
    return await service.chat_stream(chat_request.thread_id, user_id, chat_request.message)