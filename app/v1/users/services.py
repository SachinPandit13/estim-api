from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.v1.users.models import User
from app.v1.users.schemas import UserCreate, UserUpdate
from app.v1.auth.functions import get_password_hash


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
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing and not existing.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        hashed = get_password_hash(payload.password) if payload.password else None

        if existing and existing.is_deleted:
            existing.is_deleted = False
            existing.is_active = payload.is_active
            existing.role = payload.role
            existing.full_name = payload.full_name or existing.full_name
            if hashed:
                existing.hashed_password = hashed
            user = existing
        else:
            user = User(
                email=payload.email,
                hashed_password=hashed,
                full_name=payload.full_name,
                role=payload.role,
                is_active=payload.is_active,
            )
            db.add(user)

        db.commit()
        db.refresh(user)
        return user

