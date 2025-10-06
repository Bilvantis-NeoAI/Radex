from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.core.security import decode_access_token
from app.models import User
from app.schemas import TokenData
from firebase_admin import auth

oauth2_scheme_standard = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_okta = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/okta_login")


async def get_current_okta_user(
    token: str,
    db: Session = Depends(get_db)
) -> User:

    print("Received token:", token)
    decoded_token = auth.verify_id_token(token)
    print("Decoded token:", decoded_token)
    email = decoded_token.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token: missing email")

    # Query the DB for the user
    okta_user = db.query(User).filter_by(email=email).first()
    if not okta_user:
        raise HTTPException(status_code=404, detail="User not found")

    return okta_user

async def get_current_user_standard(
    token: str,
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
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
    
async def get_current_user(request: Request,
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Manually extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise credentials_exception
    token = auth_header.split("Bearer ")[1]

    # Determine which OAuth2 scheme to use based on login_type_ctx
    login_type = request.headers.get("X-Login-Type", "radex")   
    # print(login_type)
    if login_type.lower() == "okta":
        user = await get_current_okta_user(token=token,db=db)
    else:
        user = await get_current_user_standard(token=token,db=db)
    
    return user
    
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
