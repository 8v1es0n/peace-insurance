from uuid import UUID

from fastapi.sse import ServerSentEvent
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph.state import CompiledStateGraph
from .exceptions import ChatThreadNotFoundError
from .models import Chat
from .repository import ChatRepository
from .schemas import ChatHistoryResponse, ChatMessageResponse


class ChatService:
    def __init__(self, session:AsyncSession, agent: CompiledStateGraph):
        self.session = session
        self.repository = ChatRepository(self.session)
        self.agent = agent
    """会话服务"""
    # 创建对话业务逻辑实现
    async def create_chat(self, user_id: int, title: str):
        # 基于异步上下文管理器开启事务
        async with self.session.begin():
            # 创建Chat对象
            chat = Chat(user_id=user_id, title=title)
            # 调用repository层的方法进行添加, 将chat传给它
            await self.repository.create_chat(chat)
            # 返回创建的对象
            return chat

    # 获取会话列表
    async def get_chats(self, user_id: int):
        return await self.repository.list_by_userid(user_id)

    # 修改会话标题
    async def rename(self, chat_id:UUID, user_id:int, title:str):
        # 开启事务,基于上下文管理器管理
        async with self.session.begin():
            # 根据会话id和用户id,查询对应会话
            chat:Chat | None = await self.repository.find_owned(chat_id, user_id)
            # 如果是None,抛出异常
            if chat is None:
                # 绘画不存在,异常返回第哦啊用处
                raise ChatThreadNotFoundError
            # 执行修改操作
            chat.title = title

            # 手动执行提交操作,将新数据更新到数据库
            await self.session.flush()

            # 刷新对象属性
            await self.session.refresh(chat)
        # 返回会话对象
        return chat

    # 根据id删除会话
    async def delete_chat(self, chat_id:UUID, user_id:int):
        # 基于上下文管理器,开启事务
        async with self.session.begin():
            # 查询chat对象
            chat:Chat | None = await self.repository.find_owned(chat_id, user_id)
            # 为空抛出异常
            if chat is None:
                raise ChatThreadNotFoundError
            # 删除聊天记录
            await self.agent.checkpointer.adelete_thread(str(chat_id))
            # 正确查询出会话对象后删除
            await self.repository.delete_chat(chat)


    """聊天服务"""
    async def chat_stream(self, thread_id: UUID, user_id: int, msg: str):
        # 验证消息合法性
        chat = await self.repository.find_owned(thread_id, user_id)
        # 判断是否为None
        if chat is None:
            raise ChatThreadNotFoundError

        # 通过智能体将消息发送给大模型
        # 1. 准备消息列表
        _input = {
            "messages": [HumanMessage(content=msg)]
        }
        # 准备好配置信息, 包含会话id
        _config = {
            "configurable":{"thread_id": str(thread_id)}
        }

        # 通过智能体将消息发送给大模型
        response = await self.agent.astream_events(
            _input,
            _config,
            version="v3"
        )
        # 从返回值中解析到最后一条消息，再拿出来其中的内容
        # async for message in response.messages:
        #     async for text in message.text:
        #         # 在这儿拿到一个消息片段之后，使用yield，将数据组装成SSE对象放到了一个管道（流）中，往下游流
        #         yield ServerSentEvent(event="message", data=text)
        # yield ServerSentEvent(event="done", data="END")
        async for event in response:
            method = event["method"]
            if method != "messages":
                continue
            data, metadata = event["params"]["data"]
            if metadata["langgraph_node"] == "router":
                if isinstance(data, AIMessage):
                    yield ServerSentEvent(event="message", data=data.text)
            else:
                # print(data.pretty_print())
                if isinstance(data, AIMessage):
                    yield ServerSentEvent(event="message", data=data.text)
                else:
                    if data.get("delta") and data.get("delta").get("text"):
                        yield ServerSentEvent(event="message", data=data.get("delta").get("text"))
        yield ServerSentEvent(event="done", data="END")

    async def get_history_message(self, thread_id: UUID, user_id: int):
        chat = await self.repository.find_owned(thread_id, user_id)
        if chat is None:
            raise ChatThreadNotFoundError
        # 获取历史记录
        _config = {
            "configurable": {"thread_id": str(thread_id)}
        }
        snapshot = await self.agent.aget_state(_config)
        message_list: list[BaseMessage] = snapshot.values.get("messages", [])

        # 进行对象封装
        messages: list[ChatMessageResponse] = []
        for message in message_list:
            if isinstance(message, HumanMessage):
                messages.append(
                    ChatMessageResponse(role="user", content=message.text)
                )
            if isinstance(message, AIMessage):
                messages.append(
                    ChatMessageResponse(role="assistant", content=message.text)
                )
            else:
                continue
        return ChatHistoryResponse(thread_id=thread_id, messages=messages)