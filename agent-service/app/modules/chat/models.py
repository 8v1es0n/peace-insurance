from uuid import UUID, uuid4

from sqlalchemy import BigInteger, String, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin, UpdateAtMixin


# 定义与数据库中表的映射类
class Chat(Base, CreateAtMixin, UpdateAtMixin):
    # 根据表名进行映射
    __tablename__ = "chat_threads"

    # UUID类型的id
    id: Mapped[UUID] = mapped_column(
        # 数据库中的类型
        PG_UUID(as_uuid=True),
        # 主键
        primary_key=True,
        # 默认使用uuid4生成id
        default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(
        String(200), nullable=False,
        default="新会话",
        server_default="新会话"
    )