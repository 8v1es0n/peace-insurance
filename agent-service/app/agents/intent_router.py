from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from app.agents.schema import IntentResult
from app.core.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)
# 寒暄的固定回复
SOCIAL_RESPONSES = {
    "greeting": "您好，我是您的保险顾问，可以帮您咨询产品、推荐方案或办理理赔。",
    "thanks": "不客气，后续有保险问题可以随时问我。",
    "goodbye": "好的，后续需要帮助时随时联系我。",
}

SYSTEM_PROMPT = """
    你是保险商城智能客服的意图识别节点，请判断用户消息应该交给哪个工作流。

    intent只能从以下选项中选择：
    - recommendation_plan：保险产品咨询、产品条款、保险推荐、方案管理和投保咨询
    - claim：报案、理赔责任、理赔材料、理赔流程和理赔进度
    - human_handoff：投诉、高风险问题或用户明确要求人工服务
    - chitchat：与保险业务无关的普通聊天
    - fallback：无法判断用户意图
    """.strip()


class IntentRouter:
    def __init__(self):
        # 1. 普通模式
        self.model = init_chat_model(
            model="deepseek-flash",
            api_key=settings.llm.api_key,
            extra_body={
                "thinking":{"type":"disabled"}
            }
        )

        # 2. 结构化输出模型
        self.model_with_structured_output = self.model.with_structured_output(IntentResult)
    async def intent(self, message:str, context:str):
        # 1. 寒暄识别
        response:AIMessage = await self.model.ainvoke(f"""
                    根据用户的问题，进行寒暄识别，具体是问候语、致谢词、再见。
                    如果识别成功，返回对应分类：greeting、thanks、goodbye。
                    如果没有给我返回fail即可。
                    用户问题：{message}

                    注意：你能返回的数据只有字符串类型的greeting、thanks、goodbye、fail，不要随意增加修饰词，同时，不是寒暄问题也不要强制挂钩
                    """)
        if response.text != "fail":
            return SOCIAL_RESPONSES[response.text]
        # 意图识别
        try:
            intent_result = await self.model_with_structured_output.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"上下文信息:{context}, 用户的问题:{message}",)
            ])
            return intent_result
        except Exception as e:
            # 如果识别失败 - 走向fallback节点
            logger.error("意图识别出现问题了~")
            return IntentResult(
                intent="fallback",
                reason="意图识别失败"
            )
