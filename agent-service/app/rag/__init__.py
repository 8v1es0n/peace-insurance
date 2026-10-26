# 1.创建向量模型
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_milvus import Milvus, BM25BuiltInFunction
from langchain_ollama import OllamaEmbeddings

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.pipeline import RAGPipeline
from app.rag.retriever import RagRetriever

logger = get_logger(__name__)

# embeddings = OllamaEmbeddings(
#     model="qwen3-embedding:0.6b",
#     dimensions=1024,
#     base_url="http://192.168.16.224:11434"
# )

embeddings = DashScopeEmbeddings(
    model="qwen3.7-text-embedding"
)


# 2.创建向量数据库
vector_store = Milvus(
    embedding_function=embeddings,
    collection_name="insurance_collection",
    connection_args={"uri":settings.rag.milvus_url},
    vector_field=["dense", "sparse"],
    builtin_function=BM25BuiltInFunction(
        input_field_names="text",
        output_field_names="sparse",
        analyzer_params={"type":"chinese"},
        function_name="insurance_sparse_function"
    )
)

# 3.初始化流水线
pipeline = RAGPipeline(vector_store)

# 4.初始化检索器
retriever = RagRetriever(vector_store)

# 5.定义释放资源的函数
def close():
    pipeline.close()
    vector_store.client.close()
    logger.info("RAG资源释放完成~")

__all__ = ["pipeline", "retriever", "close"]

logger.info("RAG资源加载完成~")