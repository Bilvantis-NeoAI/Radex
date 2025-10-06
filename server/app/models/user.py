from sqlalchemy import Column, String, Boolean, DateTime, func, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid
from sqlalchemy.orm import relationship
# Enum for auth_provider
from sqlalchemy import Enum
 
auth_type_enum = Enum('radex', 'okta', name='auth_type')

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String(255), primary_key=True)
    auth_provider = Column(auth_type_enum, nullable=False, server_default="radex")
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=True)
    groups = Column(ARRAY(String), nullable=True)
    roles = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_logged_in = Column(DateTime(timezone=True), nullable=True)

    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
