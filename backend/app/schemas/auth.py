from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: str
    name: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
