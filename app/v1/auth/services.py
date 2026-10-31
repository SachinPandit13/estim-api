import os
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.v1.users.models import User
from app.v1.auth.schemas import LoginRequest, AdminRegisterRequest
from app.v1.auth.functions import verify_password, get_password_hash, create_access_token


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

    @staticmethod
    def register_admin(db: Session, payload: AdminRegisterRequest) -> tuple[str, User]:
        # Optional bootstrap secret validation if configured in environment
        bootstrap_secret = os.getenv("ADMIN_BOOTSTRAP_SECRET")
        if bootstrap_secret and payload.admin_secret_key != bootstrap_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin bootstrap secret key",
            )

        # Check for existing active user
        existing_user = db.query(User).filter(User.email == payload.email).first()
        if existing_user and not existing_user.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        hashed_password = get_password_hash(payload.password)

        if existing_user and existing_user.is_deleted:
            # Reactivate soft-deleted user as admin
            existing_user.is_deleted = False
            existing_user.is_active = True
            existing_user.role = "admin"
            existing_user.hashed_password = hashed_password
            if payload.full_name:
                existing_user.full_name = payload.full_name
            user = existing_user
        else:
            user = User(
                email=payload.email,
                hashed_password=hashed_password,
                full_name=payload.full_name,
                role="admin",
                is_active=True,
                is_deleted=False,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
        return token, user

