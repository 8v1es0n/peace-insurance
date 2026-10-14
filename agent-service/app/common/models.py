from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from sqlalchemy import DateTime, func

# 1. 定义基类
class Base(DeclarativeBase):
    def __repr__(self) -> str:
        """通用的repr函数，用于控制台输出对象信息"""
        # 获取当前实例的类名（如 User、Order 等）
        cls_name = self.__class__.__name__
        # 初始化空字典，用于存储非私有属性及其值
        attrs = {}
        # 遍历实例的所有属性和值（包括私有属性和数据库字段）
        for key, val in vars(self).items():
            # 跳过以下划线开头的私有属性（如 _sa_instance_state）
            if key.startswith("_"):
                continue
            # 如果属性值是 datetime 类型，则格式化为易读的字符串
            if isinstance(val, datetime):
                attrs[key] = val.strftime("%Y-%m-%d %H:%M:%S")
            # 其他类型的值直接存入字典
            else:
                attrs[key] = val
        # 返回格式化的字符串，例如：User({'id': 1, 'name': 'Alice'})
        return f"{cls_name}({attrs})"


# 2. 定义混入类
class CreateAtMixin:
    created_at: Mapped[datetime] = mapped_column( # mapped_column映射表中的字段
        # onupdate=func.now() 会在每次数据行被 UPDATE 时，由 SQLAlchemy 自动更新该字段
        DateTime(timezone=True),
        server_default=func.now()
    )


class UpdateAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )