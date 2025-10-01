from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.core.security import decode_access_token
from app.models import User, OktaUser
from app.schemas import TokenData
from firebase_admin import auth

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/okta_login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user

# Dependency to get current active Okta user
async def get_current_okta_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> OktaUser:
    print("Received token:", token)
    decoded_token = auth.verify_id_token(token)
    print("Decoded token:", decoded_token)
    email = decoded_token.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token: missing email")

    # Query the DB for the user
    okta_user = db.query(OktaUser).filter_by(email=email).first()
    if not okta_user:
        raise HTTPException(status_code=404, detail="User not found")

    return okta_user
    
async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

async def get_current_okta_superuser(
    current_user: OktaUser = Depends(get_current_okta_user)
) -> OktaUser:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions for Okta user"
        )
    return current_user
