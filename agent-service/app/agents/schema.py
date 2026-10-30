# 1.定义节点的名称
from typing import Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

Intent = Literal[
    "chitchat",  # 聊天节点名称
    "recommendation_plan",  # 保险推荐节点名称
    "claim",  # 理赔节点名称
    "human_handoff",  # 人工客服节点名称
    "fallback",  # 意图识别失败之后的节点名称
]

# 2.定义主图的流转状态
class InsuranceAgentState(MessagesState):
    # 1.上一轮会话意图识别的结果
    previous_workflow: str
    # 2.本轮对话意图识别的结果
    active_workflow: str

class IntentResult(BaseModel):
    # 1.意图识别的结果
    intent: str = Field(description="本轮对话意图识别的结果")
    # 2.判断依据
    reason: str = Field(description="意图识别的依据、原因")