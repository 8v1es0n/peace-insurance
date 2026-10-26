from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from mineru import MinerU
from app.core.config import settings, APP_ROOT
from app.core.logging import get_logger
from app.infra.database import AsyncSessionFactory
from app.modules.product.models import Product
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository

logger = get_logger(__name__)

MARKDOWN_OPTIMIZATION_PROMPT = """
下面这份Markdown文档是从保险条款PDF解析得来，由于PDF中的各个小节是以表格形式存在，所以解析时出现错乱。你分析内容，帮我转为格式正确的Markdown，特别是标题编号要正确。
- 标题等级要从1级标题开始，逐层增加，目录和文档名不计入标题等级。
- 输出结果中不要包含正文开始之前的部分。
- 输出结果只包含Markdown正文，不要解释或代码围栏。
- 不要修改保险条款。
""".strip()


class RAGPipeline:
    def __init__(self, vector_store: Milvus):
        self.vector_store = vector_store
        self.mineru = MinerU(settings.rag.mineru_token)

        self.model = init_chat_model(
            model="deepseek-v4-flash",
            model_provider="deepseek",
            api_key=settings.llm.api_key,
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=10000
        )

        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3")
            ],
            # 不在正文中包含标题, 所有标题都存储在元数据中
            strip_headers=True
        )

        self.splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", ",", ""],

            # 每一个子块的目标大小
            chunk_size=400,
            # 滑动窗口的大小
            chunk_overlap=50
        )
        logger.info("RAGPipeline初始化成功~")


    async def ingest(self, product: Product):
        logger.info(f"开始处理产品: {product}")
        # 1. 文件加载
        markdown = self._file_load(product.clause_name)
        # 2. 文本切分
        parent_chunk_list, children_chunk_list = self._chunks(markdown, product)
        # 3. 子块存入向量数据库
        self.save_milvus(product.id, children_chunk_list)
        # 4. 父块存入普通数据库
        await self.save_db(product.id, parent_chunk_list)


    def _file_load(self, clause_name):
        logger.info(f"1. 开始加载文档~")
        print(clause_name)
        clause_file_path = f"{APP_ROOT}/data/raw/kb/{clause_name}"
        with open(clause_file_path.replace("kb","final").replace("pdf","md"), "r", encoding="utf-8") as f:
            markdown = f.read()
        logger.info(f"2. 得到最终文档")
        # logger.info(f"2. 得到最终文档:{markdown}")
        return markdown


    def _chunks(self, markdown, product: Product):
        logger.info("3. 开始切片~")
        parent_chunks = self.md_splitter.split_text(markdown)

        parent_chunk_list: list[ParentChunk] = []
        children_chunk_list: list[Document] = []

        for parent_chunk in parent_chunks:
            section_path = list(parent_chunk.metadata.values())

            parent_chunk_obj = ParentChunk(
                id=uuid4(), product_id=product.id, clause_name=product.clause_name,
                section_path=section_path, content=parent_chunk.page_content
            )
            parent_chunk_list.append(parent_chunk_obj)

            children_chunks = self.splitter.split_documents([parent_chunk])

            header_row = ""
            for section in section_path:
                header_row += section + "\n"

            for children_chunk in children_chunks:
                children_chunk.metadata = {
                    "parent_id": str(parent_chunk_obj.id),
                    "product_id": product.id
                }
                children_chunk.page_content = header_row + children_chunk.page_content
            children_chunk_list.extend(children_chunks)

        logger.info(f"父块数量：{len(parent_chunk_list)}")
        logger.info(f"子块数量：{len(children_chunk_list)}")
        return parent_chunk_list, children_chunk_list


    def save_milvus(self, product_id, children_chunk_list):
        logger.info("4. 子块写入向量数据")
        if self.vector_store.client.has_collection(
            self.vector_store.collection_name
        ):
            self.vector_store.delete(expr=f"product_id == {product_id}")
        # self.vector_store.add_documents(children_chunk_list)
        # 调用云端模型, 分批请求
        batch_size = 20
        for start in range(0, len(children_chunk_list), batch_size):
            batch = children_chunk_list[start: start + batch_size]
            self.vector_store.add_documents(batch)
            logger.info(
                f"产品 {product_id} 向量写入进度："
                f"{min(start + batch_size, len(children_chunk_list))}"
                f"/{len(children_chunk_list)}"
            )


    async def save_db(self, product_id, parent_chunk_list):
        logger.info("5. 父块写入PostgreSQL数据库")
        async with AsyncSessionFactory() as session:
            async with session.begin():
                repository = ParentChunkRepository(session)
                await repository.delete_by_product_id(product_id)
                repository.add_all(parent_chunk_list)

    def close(self):
        self.mineru.close()
        logger.warn("Pipeline资源关闭完成~")