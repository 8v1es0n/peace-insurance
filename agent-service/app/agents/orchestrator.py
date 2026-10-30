from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.types import Command

from app.agents.chitchat import ChitchatAgent
from app.agents.insurance_advisor import init_insurance_advisor
from app.agents.intent_router import IntentRouter
from app.agents.schema import InsuranceAgentState, Intent, IntentResult
from app.core.logging import get_logger

logger = get_logger(__name__)

def search_previous_ai_message(messages:list[BaseMessage]) -> str:
    """
    从下往上从历史消息中拿到最后一条AI的回答
    :param messages: 历史消息记录
    :return: 最后一条AI回答的内容
    """
    # 1. 反转消息
    messages = messages[::-1]
    for message in messages:
        # 2.1 如果消息不是AIMessage, 不要
        if not isinstance(message, AIMessage):
            continue
        # 2.2 如果消息中包含tool_calls, 工具调用也不要
        if message.tool_calls:
            continue
        # 2.3 最后一个AI消息
        if message.text:
            return message.text
    return ""

# 定义节点
# 1.1 定义路由节点
async def router_node(state:InsuranceAgentState) -> Command[Intent]:
    # 1 获取上一轮会话的意图识别结果
    previous_workflow = state.get("active_workflow", "")
    # 2 得到本轮对话的意图识别结果
    # 2.1 拼接上下文
    previous_ai_message = search_previous_ai_message(state["messages"])
    context = f"上一轮对话的意图识别结果: {previous_workflow}, 上一轮对话AI的回答: {previous_ai_message}"
    # 2.2 先获取到最新的用户消息
    last_human_message = state["messages"][-1].content
    # 2.3 调用意图识别的方法
    intent_result: str | IntentResult = await IntentRouter().intent(last_human_message, context)
    if isinstance(intent_result, str):

        return Command(
            update={
                "messages":[AIMessage(content=intent_result)],
                "previous_workflow":previous_workflow,
                "active_workflow":"chitchat"
            },
            goto=END
        )
    # 3. 返回Command
    return Command(
        update={
            "previous_workflow":previous_workflow,
            "active_workflow":intent_result
        },
        goto=intent_result.intent
    )


# 1.2 保险推荐节点
def recommendation_plan_node(state:InsuranceAgentState):
    return {
        "messages":[AIMessage(content="保险推荐功能暂未提供~")]
    }
# 1.3 理赔节点
def claim_node(state:InsuranceAgentState):
    return {
        "messages": [AIMessage(content="理赔功能暂未提供~")]
    }
# # 1.4 闲聊节点
# def chitchat_node(state:InsuranceAgentState):
#     return {
#         "messages": [AIMessage(content="客官，聊两块钱的~")]
#     }
# 1.5 人工客服节点
def handoff_node(state:InsuranceAgentState):
    return {
        "messages": [AIMessage(content="我们办法处理你的请求，我会将你的问题转交人工客服处理~")]
    }
# 1.6 意图识别失败的节点
def fallback_node(state:InsuranceAgentState):
    return {
        "messages": [AIMessage(content="我现在没有办法识别出来你要干什么，请重新问问题...")]
    }

# 2.定义交给FastAPI生命周期管理的智能体创建函数
def init_insurance_agent(checkpointer: AsyncPostgresSaver):
    # 2.1 定义智能体创建器
    builder = StateGraph(InsuranceAgentState)
    # 2.2 添加节点
    builder.add_node("router", router_node)
    builder.add_node("chitchat", ChitchatAgent().builder())
    builder.add_node("recommendation_plan", init_insurance_advisor())
    builder.add_node("claim", claim_node)
    builder.add_node("human_handoff", handoff_node)
    builder.add_node("fallback", fallback_node)

    # 2.3 添加边
    builder.add_edge(START, "router")
    builder.add_edge("chitchat", END)
    builder.add_edge("recommendation_plan", END)
    builder.add_edge("claim", END)
    builder.add_edge("human_handoff", END)
    builder.add_edge("fallback", END)

    # 2.4 编程智能体
    agent = builder.compile(checkpointer=checkpointer)

    logger.info("基于LangGraph的智能体创建完成")

    return agent