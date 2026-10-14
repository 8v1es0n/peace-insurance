from decimal import Decimal

from pydantic import BaseModel


# 请求模型


# 响应模型
class ProductResponse(BaseModel):
    id: int
    name: str
    clause_name: str
    category: str
    insurer: str
    image_url: str
    description: str
    min_premium: Decimal | None
    max_premium: Decimal | None
    target_group: str | None
    highlights: list[str]
    status: str