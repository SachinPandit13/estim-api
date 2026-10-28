from typing import Optional
from sqlalchemy.orm import Session
from app.v1.users.models import User
from app.v1.auth.schemas import LoginRequest
from app.v1.auth.functions import verify_password, create_access_token


class AuthService:
    @staticmethod
    def authenticate(db: Session, payload: LoginRequest) -> Optional[tuple[str, User]]:
        user = db.query(User).filter(User.email == payload.email, User.is_deleted == False).first()
        if not user or not user.hashed_password:
            return None
        if not verify_password(payload.password, user.hashed_password):
            return None
        token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
        return token, user
