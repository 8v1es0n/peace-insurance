# 定义闲聊子节点的状态
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph

from app.agents.schema import InsuranceAgentState
from app.core.config import settings


class ChitchatState(InsuranceAgentState):
    chitchat_count: int  # 闲聊的次数

MAX_CHITCHAT_COUNT = 3

class ChitchatAgent:
    def __init__(self):
        # 1.初始化模型
        self.model = init_chat_model(
            model="deepseek-v4-flash",
            api_key=settings.llm.api_key,
            extra_body={"thinking":{"type":"disabled"}}
        )

    async def handle_chat(self, state:ChitchatState):
        # 1. 获取已有的聊天次数
        count = state.get("chitchat_count", 0)
        # 2. 判断上一个流程是否为聊天,如果不是聊天次数重置
        if state["previous_workflow"] != "chitchat":
            count = 0
        # 如果是聊天已经超过了最大次数, 返回一个固定回答
        if count >= MAX_CHITCHAT_COUNT:
            return {
                "messages":[AIMessage(content="我主要协助处理保险产品、投保和理赔咨询，请告诉我想办理或了解的事项。")]
            }
        # 4. 与大模型进行交互
        response: AIMessage = await self.model.ainvoke([
            SystemMessage(content=""),
            *state["messages"]
        ])

        return {
            "messages":[response],
            "chitchat_count":count + 1
        }


    def builder(self):
        # 1.创建构建器
        builder = StateGraph(ChitchatState)
        # 2.添加节点
        builder.add_node("handler_chitchat", self.handle_chat)
        # 3.添加边构建图
        builder.set_entry_point("handler_chitchat")
        builder.set_finish_point("handler_chitchat")
        # 4.编译智能体
        agent = builder.compile(checkpointer=True)

        return agent