from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.models import ParentChunk


class ParentChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 1. 根据产品ID删除数据
    async def delete_by_product_id(self, product_id:int):
        # 1. 准备SQL语句\
        sql = delete(ParentChunk).where(ParentChunk.product_id == product_id)
        # 2. 执行SQL语句
        await self.session.execute(sql)

    # 2. 批量新增数据
    def add_all(self, parent_chunk_list:list[ParentChunk]):
        self.session.add_all(parent_chunk_list)


    # 3. 根据子块的父块查询父块中的
    async def list_by_ids(self, ids: list[str]) -> list[ParentChunk]:
        # 准备SQL
        sql = select(ParentChunk).where(ParentChunk.id.in_(ids))
        # 执行SQL
        execute_result = await self.session.execute(sql)
        # 解析结果
        return list(execute_result.scalars().all())