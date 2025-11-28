"""
MCP (Model Context Protocol) Models

Database models for MCP data analysis functionality
tracking chat sessions, queries, and file metadata.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class McpChatSession(Base):
    """Chat session for tracking MCP interactions"""
    __tablename__ = "mcp_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship with queries
    queries = relationship("McpQueryHistory", back_populates="session", cascade="all, delete-orphan")


class McpQueryHistory(Base):
    """Query history and responses for MCP chat sessions"""
    __tablename__ = "mcp_query_histories"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("mcp_chat_sessions.session_id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    source_info = Column(JSON, nullable=True)  # Store source attribution metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to session
    session = relationship("McpChatSession", back_populates="queries")


class McpFileMetadata(Base):
    """Metadata for uploaded MCP files"""
    __tablename__ = "mcp_file_metadata"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    folder_id = Column(String, nullable=True, index=True)
    filename = Column(String, nullable=False)
    object_name = Column(String, nullable=False)  # MinIO object path
    file_type = Column(String, nullable=False)  # 'csv' or 'excel'
    file_size = Column(Integer, nullable=False)
    row_count = Column(Integer, nullable=False)
    columns = Column(JSON, nullable=False)  # List of column names
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class McpQueryAnalytics(Base):
    """Analytics for MCP query usage (optional)"""
    __tablename__ = "mcp_query_analytics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    query_count = Column(Integer, default=0)
    session_count = Column(Integer, default=0)
    last_query_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
