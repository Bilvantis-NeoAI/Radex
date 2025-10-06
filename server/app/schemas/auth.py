from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

class AuthProvider(str, Enum):
    radex = "radex"
    okta = "okta"

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    auth_provider: AuthProvider = AuthProvider.radex
    groups: Optional[List[str]] = None  # only for Okta users
    roles:Optional[List[str]] = None
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(BaseModel):
    user_id: Optional[str] = None
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    auth_provider: AuthProvider = AuthProvider.radex
    groups: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    is_active: bool = True
    # is_superuser removed for security - only set via database/admin

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    auth_provider: Optional[AuthProvider] = None
    groups: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserInDB(UserBase):
    user_id: str
    last_logged_in: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class User(UserInDB):
    pass

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
