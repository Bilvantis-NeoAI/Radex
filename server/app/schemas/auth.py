from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    is_active: bool = True
    # is_superuser removed for security - only set via database/admin

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserInDB(UserBase):
    id: UUID
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

class OktaUserSchema(BaseModel):
    okta_user_id: str
    email: EmailStr
    first_name: str
    last_name: str
    groups: Optional[List[str]] = None
    roles: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

    class Config:
        orm_mode = True

class OktaUserUpdate(BaseModel):
    okta_user_id: str  # required to identify the user
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    groups: Optional[List[str]] = None
    roles: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    
    class Config:
        orm_mode = True

class OktaUser(OktaUserSchema):
    pass