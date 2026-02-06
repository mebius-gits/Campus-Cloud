"""Token 與通用模型"""

from sqlmodel import Field, SQLModel


# Generic message
class Message(SQLModel):
    """通用訊息回應"""

    message: str


# JSON payload containing access token
class Token(SQLModel):
    """JWT 存取權杖回應"""

    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    """JWT Token 內容"""

    sub: str | None = None


class NewPassword(SQLModel):
    """重設密碼請求"""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


__all__ = [
    "Message",
    "Token",
    "TokenPayload",
    "NewPassword",
]
