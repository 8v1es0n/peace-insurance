from langchain_core.messages import HumanMessage
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model


async def init_connection_pool():
    # 创建连接池
    checkpoint_pool = AsyncConnectionPool(
        conninfo=settings.db.checkpointer_url,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row
        },
        open=False
    )

    # 初始化连接
    await checkpoint_pool.open()
    # 等待连接池就绪
    await checkpoint_pool.wait()

    return checkpoint_pool

async def init_checkpointer(checkpoint_pool):
    # 初始化checkpointer
    checkpointer = AsyncPostgresSaver(checkpoint_pool)
    # 自动建表（与checkpointer存储有关的表）
    await checkpointer.setup()

    return checkpointer

async def init_chat(agent, config, msg):
    response = await agent.ainvoke(
        {
            "messages": [HumanMessage(content=msg)]
        },
        config
    )
    for message in response["messages"]:
        message.pretty_print()


def init_agent(checkpointer):
    # 准备模型
    load_dotenv()
    model = init_chat_model(model="deepseek-v4-flash")

    # 创建智能体
    agent = create_agent(model=model, checkpointer=checkpointer)

    return agent


async def main():
    checkpoint_pool = await init_connection_pool()
    checkpointer = await init_checkpointer(checkpoint_pool)
    agent = init_agent(checkpointer)
    _config = {"configurable": {"thread_id": "1"}}
    # print("==========第一轮对话==========")
    # await init_chat(agent, _config, "我现在有12个苹果，有3个人，如何分配?")
    # print("==========第二轮对话==========")
    # await init_chat(agent, _config, "我现在有12个苹果，有4个人，如何分配?")

    # 获取历史消息记录
    # snapshot = await agent.aget_state(_config)
    # print(type(snapshot))
    # messages = snapshot.values.get("messages", [])
    # for message in messages:
    #     message.pretty_print()

    # 删除历史消息记录
    thread_id = _config["configurable"]["thread_id"]
    await checkpointer.adelete_thread(thread_id)

    snapshot = await agent.aget_state(_config)
    print(snapshot.values)


if __name__ == '__main__':
    # Windows 下 psycopg 异步必须用 SelectorEventLoop，显式指定 loop_factory
    import asyncio
    import selectors
    asyncio.run(
        main(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
    )