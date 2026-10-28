from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.auth.schemas import LoginRequest, AdminRegisterRequest, TokenResponse
from app.v1.auth.services import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = AuthService.authenticate(db, payload)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token, user = result
    return TokenResponse(access_token=token, user=user)


@router.post(
    "/register-admin",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Admin User",
    description="Provision an administrator account and return an authenticated bearer token.",
)
def register_admin(payload: AdminRegisterRequest, db: Session = Depends(get_db)):
    token, user = AuthService.register_admin(db, payload)
    return TokenResponse(access_token=token, user=user)
