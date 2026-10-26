from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from langchain.tools import tool
from app.core.logging import get_logger
from app.infra.database import AsyncSessionFactory
from app.modules.product.models import Product
from app.modules.product.service import ProductService
from app.rag.models import ParentChunk

logger = get_logger(__name__)

@tool
async def query_candidate_products(
    categories: list[str],
    premium_min: Decimal | None = None,
    limit_per_category: int = 5
):
    """
        根据险种和保费条件查询可用于推荐的候选保险产品。当用户咨询具体保险产品或需要保险产品推荐时使用。

        Args:
            categories: 产品分类列表，可选值为 medical、critical_illness、life、accident。
            premium_min: 最低保费上限，可选参数，只返回最低保费小于该值的产品。
            limit_per_category: 每个险种最多返回的产品数量，可选参数，默认5。
    """
    logger.info("保险推荐工具被调用~")
    async with AsyncSessionFactory() as session:
        service = ProductService(session)
        products_list: list[Product] = await service.find_by_candidates(categories, premium_min, limit_per_category)
        return jsonable_encoder(products_list)

@tool
async def query_product_clause(query:str, product_id:int):
    """
    查询指定保险产品的条款内容。
    Args:
        query: 需要从保险条款中查询的问题。
        product_id: 保险产品ID
        k:最终需要的条款数量
    """
    logger.info("保险条款查询的工具已经被调用了~")
    # 1. 导入检索器 - 不会重新创建retriever
    from app.rag import retriever
    # 2. 执行调用
    parent_chunk_list:list[ParentChunk] = await retriever.retriever(query, product_id)

    # 3. 将父块组装成字符串, 返回给大模型
    response_str = ""
    for parent_chunk in parent_chunk_list:
        # 3.1 先组装标题行
        header_row = ""
        for section in parent_chunk.section_path:
            header_row += section + "\n"
        # 3.2 再组装父块的正文文本
        response_str += header_row + parent_chunk.content

    # 4. 返回给大模型
    return response_str
