from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product.repository import ProductRepository


class ProductService:
    def __init__(self, session:AsyncSession):
        self.session = session
        self.repository = ProductRepository(session)

    # 查询产品列表
    async def find_by_category(self, category:str | None):
        product_list = await self.repository.find_by_category(category)
        return product_list

    # 产品条件查询方法
    async def find_by_candidates(self, categories:list[str],
                                 premium_min:Decimal | None, limit_per_category:int):
        # 1.险种去重
        categories = dict.fromkeys(categories)

        # 循环查询每一种险种
        all_product = []
        for category in categories:
            product_list = await self.repository.find_by_candidates(category, premium_min, limit_per_category)
            all_product.extend(product_list)
        return all_product
