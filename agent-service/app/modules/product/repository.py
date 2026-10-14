from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product.models import Product


# 定义类 ProductRepository
class ProductRepository:
    # 定义初始化__init__魔法方法
    def __init__(self, session:AsyncSession):
        self.session = session

    # 定义查询方法
    async def find_by_category(self, category:str):
        # 组装查询条件
        conditions = [Product.status == "active"]
        # 扩展：自己没有的数据
        # 需要别人在调用的时候传递给我 - 参数
        # 在创建我自己这个对象的时候 - 实例属性
        if category:
            conditions.append(Product.category == category)
        # 2.2 准备SQL语句
        # conditions = [Product.status == "active", Product.category == category]
        sql = select(Product).where(*conditions).order_by(Product.id.asc())
        # 2.3 执行SQL语句
        exec_result = await self.session.execute(sql)
        # 2.4 拿到具体的数据
        product_list = exec_result.scalars().all()
        # 2.5 返回调用处查询结果
        return list(product_list)


    # 定义产品条件查询方法
    async def find_by_candidates(self, category:str, premium_min: Decimal | None, limit_per_category: int):
        # 组合查询条件
        conditions = [
            Product.category == category,
            Product.status == "active"
        ]

        if premium_min:
            conditions.append(Product.min_premium < premium_min)

        sql = select(Product).where(*conditions).order_by(Product.min_premium.desc()).limit(limit_per_category)
        # 执行查询语句
        exec_result = await self.session.execute(sql)
        # 返回到具体数据
        return exec_result.scalars().all()