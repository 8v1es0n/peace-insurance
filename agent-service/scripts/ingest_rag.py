import asyncio
import sys
from pathlib import Path

from langchain_community.embeddings import DashScopeEmbeddings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_ollama import OllamaEmbeddings

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.database import close_database, AsyncSessionFactory
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.rag.pipeline import RAGPipeline


logger = get_logger(__name__)


def create_vector_store() -> Milvus:
    # embeddings = OllamaEmbeddings(
    #     model="qwen3-embedding:0.6b",
    #     dimensions=1024,
    # )

    embeddings = DashScopeEmbeddings(
        model="qwen3.7-text-embedding"
    )

    return Milvus(
        embedding_function=embeddings,
        collection_name="insurance_collection",
        builtin_function=BM25BuiltInFunction(
            analyzer_params={"type": "chinese"}
        ),
        vector_field=["dense", "sparse"],
        connection_args={"uri": settings.rag.milvus_url},
        auto_id=True,
    )


async def find_all_products() -> list[Product]:
    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        return await repository.find_by_category(None)


async def main() -> None:
    vector_store = create_vector_store()
    pipeline = RAGPipeline(vector_store)

    try:
        products = await find_all_products()
        logger.info("开始构建RAG知识库", product_count=len(products))

        for index, product in enumerate(products, start=1):
            logger.info(
                "开始处理保险产品",
                progress=f"{index}/{len(products)}",
                product_id=product.id,
                product_name=product.name,
            )
            await pipeline.ingest(product)

        logger.info("RAG知识库构建完成", product_count=len(products))
    finally:
        pipeline.close()
        vector_store.client.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())