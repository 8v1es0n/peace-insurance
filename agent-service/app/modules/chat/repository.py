from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Chat


# 定义操作数据库表的类
class ChatRepository:
    # 初始化实例属性
    def __init__(self, session: AsyncSession):
        self.session = session

    # 新增绘画
    # 上层封装一个Chat,以便我们使用
    async def create_chat(self, chat: Chat):
        self.session.add(chat)

    # 根据userid查询会话列表
    async def list_by_userid(self, user_id: int):
        # 准备SQL语句
        sql = select(Chat).where(Chat.user_id == user_id).order_by(Chat.updated_at.desc(), Chat.created_at.desc())
        # 执行SQL语句
        chats = await self.session.scalars(sql)
        return list(chats.all())

    # 查询会话所有者
    async def find_owned(self, chat_id:UUID, user_id:int):
        # 准备SQL语句
        sql = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        # 执行SQL语句
        result = await self.session.execute(sql)
        # 返回执行的结果
        return result.scalars().one_or_none()

    # 删除会话
    async def delete_chat(self, chat:Chat):
        # 删除操作
        await self.session.delete(chat)