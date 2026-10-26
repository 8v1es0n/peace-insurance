from uuid import UUID
from sqlalchemy import UUID as PG_UUID, BigInteger, ARRAY, Text, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin


class ParentChunk(Base, CreateAtMixin):
    """父块"""

    __tablename__ = "parent_chunks"

    id:Mapped[UUID] = mapped_column(PG_UUID, primary_key=True)
    product_id:Mapped[int] = mapped_column(BigInteger, nullable=False)
    section_path:Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=[])
    content:Mapped[str] = mapped_column(Text, nullable=False)
    clause_name:Mapped[str] = mapped_column(String(300), nullable=False)