from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product.repository import ProductRepository


class ProductService:
    def __init__(self, session:AsyncSession):
        self.session = session
        self.repository = ProductRepository(session)

    async def find_by_category(self, category:str | None):
        product_list = await self.repository.find_by_category(category)
        return product_list