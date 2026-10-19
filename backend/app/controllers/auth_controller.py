from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import UserRegister, UserLogin, Token, UserResponse
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Resolves the authenticated user from the Bearer JWT token.
    Falls back to a default persistent workspace user for smooth local development.
    """
    user_id = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = AuthService.decode_access_token(token)
        if payload and "sub" in payload:
            user_id = payload["sub"]

    if user_id:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if user:
            return user

    # Development fallback: ensure a default workspace user exists
    default_user = db.query(User).filter(User.email == "researcher@evidenceai.local").first()
    if not default_user:
        hashed = AuthService.hash_password("evidenceai2026")
        default_user = User(
            id="usr_default_workspace",
            email="researcher@evidenceai.local",
            hashed_password=hashed
        )
        db.add(default_user)
        db.commit()
        db.refresh(default_user)

    return default_user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    hashed_pw = AuthService.hash_password(payload.password)
    user = User(email=payload.email, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not AuthService.verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = AuthService.create_access_token(user.id, user.email)
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=86400,
        user_id=user.id,
        email=user.email
    )

@router.get("/me", response_model=UserResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
