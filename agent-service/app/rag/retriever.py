from langchain_core.documents import Document
from langchain_milvus import Milvus
from pymilvus import Function, FunctionType

from app.infra.database import AsyncSessionFactory
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository


def create_reranker(query: str) -> Function:
    """milvus的reranker function，这里采用ali的重排模型"""
    return Function(
        name="dashscope_semantic_ranker",
        input_field_names=["text"],
        function_type=FunctionType.RERANK,
        params={
            "reranker": "model",
            "provider": "ali",
            "model_name": "qwen3.7-text-rerank",
            "queries": [query],
            "max_client_batch_size": 5,
        },
    )

class RagRetriever:
    def __init__(self, vector_store: Milvus):
        self.vector_store = vector_store

    async def retriever(self, query, product_id) -> list[ParentChunk]:
        # 1. 子块检索
        children_chunk_list = self.vector_store.similarity_search(
            query, fetch_k=5, expr=f"product_id == {product_id}",
            reranker=create_reranker(query)
        )

        # 解析父块ID
        parent_ids = list(dict.fromkeys(
                         child.metadata["parent_id"] for child in children_chunk_list
        ))
        if len(parent_ids) == 0:
            return []

        # 父块召回
        async with AsyncSessionFactory() as session:
            repository = ParentChunkRepository(session)
            parent_chunk_list = await repository.list_by_ids(parent_ids)

        # 按照子块顺序组装父块顺序
        parent_chunk_map = {
        str(parent_chunk.id) : parent_chunk
        for parent_chunk in parent_chunk_list
        }

        return [parent_chunk_map[parent_id] for parent_id in parent_ids]
