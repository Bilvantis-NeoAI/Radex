"""
Chat History Manager for MCP Module

Manages chat sessions, question-answer pairs, and source attribution
using RADEX's SQLAlchemy models and PostgreSQL storage.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.mcp import McpChatSession, McpQueryHistory


class MCPChatManager:
    """Handles chat history and session management within RADEX"""

    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: str, session_id: str) -> int:
        """Create a new chat session"""
        session = McpChatSession(
            user_id=user_id,
            session_id=session_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session.id

    def save_query(self, session_id: str, question: str, response: str,
                   source_info: Dict[str, Any] = None) -> int:
        """Save a Q&A pair to history"""
        query_history = McpQueryHistory(
            session_id=session_id,
            question=question,
            response=response,
            source_info=json.dumps(source_info or {}),
            created_at=datetime.utcnow()
        )
        self.db.add(query_history)
        self.db.commit()
        self.db.refresh(query_history)

        # Update session last activity
        session = self.db.query(McpChatSession).filter_by(session_id=session_id).first()
        if session:
            session.last_activity = datetime.utcnow()
            self.db.commit()

        return query_history.id

    def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        history = (self.db.query(McpQueryHistory)
                  .filter_by(session_id=session_id)
                  .order_by(McpQueryHistory.created_at.desc())
                  .limit(limit)
                  .all())

        # Convert to dict and reverse to chronological order
        return [
            {
                "id": entry.id,
                "question": entry.question,
                "response": entry.response,
                "source_info": json.loads(entry.source_info) if entry.source_info else {},
                "timestamp": entry.created_at.isoformat()
            }
            for entry in reversed(history)
        ]

    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent chat sessions for a user"""
        sessions = (self.db.query(McpChatSession)
                   .filter_by(user_id=user_id)
                   .order_by(McpChatSession.last_activity.desc())
                   .limit(limit)
                   .all())

        return [
            {
                "id": session.id,
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }
            for session in sessions
        ]

    def clear_session_history(self, session_id: str) -> bool:
        """Clear all chat history for a session"""
        try:
            # Delete query history
            self.db.query(McpQueryHistory).filter_by(session_id=session_id).delete()

            # Update session last activity
            session = self.db.query(McpChatSession).filter_by(session_id=session_id).first()
            if session:
                session.last_activity = datetime.utcnow()
                self.db.commit()

            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            return False

    def delete_session(self, session_id: str) -> bool:
        """Delete entire session and all history"""
        try:
            # Delete query history first (foreign key constraint)
            self.db.query(McpQueryHistory).filter_by(session_id=session_id).delete()

            # Delete session
            self.db.query(McpChatSession).filter_by(session_id=session_id).delete()

            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            return False

    def get_session_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics for MCP usage"""
        # Count sessions
        session_count = self.db.query(McpChatSession).filter_by(user_id=user_id).count()

        # Count queries
        query_count = (self.db.query(McpQueryHistory)
                      .join(McpChatSession)
                      .filter(McpChatSession.user_id == user_id)
                      .count())

        # Get date of first session
        first_session = (self.db.query(McpChatSession)
                        .filter_by(user_id=user_id)
                        .order_by(McpChatSession.created_at.asc())
                        .first())

        first_chat_date = first_session.created_at.isoformat() if first_session else None

        return {
            "total_sessions": session_count,
            "total_queries": query_count,
            "first_chat_date": first_chat_date,
            "user_id": user_id
        }
