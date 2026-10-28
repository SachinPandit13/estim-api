from typing import Optional
from sqlalchemy.orm import Session
from app.v1.users.models import User
from app.v1.users.schemas import UserCreate, UserUpdate


class UserService:
    @staticmethod
    def get_all(db: Session) -> list[User]:
        return db.query(User).filter(User.is_deleted == False).all()

    @staticmethod
    def get_by_id(db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.id == user_id, User.is_deleted == False).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email, User.is_deleted == False).first()

    @staticmethod
    def create(db: Session, payload: UserCreate) -> User:
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            is_active=payload.is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
