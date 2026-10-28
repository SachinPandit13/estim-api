from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.v1.users.schemas import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Administrator email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: Optional[str] = Field(None, description="Administrator full name")
    admin_secret_key: Optional[str] = Field(
        None,
        description="Optional bootstrap secret key for protected environments",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

