# 目标：创建保险顾问智能体 - init_insurance_agent(checkpointer:AsyncPostgresSaver)
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 准备系统提示此
SYSTEM_PROMPT="""
你是“安心保”的智能保险顾问。
你需要使用专业、准确、容易理解的语言回答用户的保险问题。
当信息不足时，应先向用户追问，不要编造保险产品或保障内容。"""

def init_insurance_agent(checkpointer: AsyncPostgresSaver):
    # 准备模型
    model = init_chat_model(
        model="deepseek-v4-flash",
        api_key=settings.llm.api_key,
        extra_body={
            "thinking":{"type": "disabled"}
        }
    )
    # 准备工具
    tools = []
    # 准备智能体
    agent = create_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        system_prompt=SYSTEM_PROMPT
    )

    logger.info("保险顾问智能体启动完成~")
    return agent