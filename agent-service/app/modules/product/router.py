# 路由层
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_async_session
from app.modules.product.schemas import ProductResponse
from app.modules.product.service import ProductService

# 1.创建APIRouter对象
router = APIRouter(prefix="", tags=["产品管理"])

# 2.定义装饰器
# 定义查询方法
@router.get("/api/v1/products", summary="查询产品列表", response_model=list[ProductResponse])
# 3.定义函数 - 接收参数和注入session
async def list_products(
        category:str | None = None,
        session:AsyncSession = Depends(get_async_session)
):
    # 4.实现代码逻辑
    # 4.1 创建service对象
    service = ProductService(session)
    # 4.2 调用对象中的方法
    product_list = await service.find_by_category(category)
    return product_list # 备注:自动将属性更多的对象，转换为属性更少的对象


# 定义产品条件查询方法
@router.get("/api/v1/products/candidates", summary="产品条件查询", response_model=list[ProductResponse])
async def products_by_category(
        categories:list[str] = Query(min_length=1), premium_min: Decimal | None = None, limit_per_category: int = 5,
        session:AsyncSession = Depends(get_async_session)
):
    service = ProductService(session)
    product_list = await service.find_by_candidates(categories, premium_min, limit_per_category)
    return product_list