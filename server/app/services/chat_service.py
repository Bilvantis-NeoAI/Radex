from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate, ChatSessionWithMessages

class ChatService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- Chat Sessions ----------

    def create_session(self, user_id: str, session_data: ChatSessionCreate = None) -> ChatSession:
        """Create a new chat session for the user"""
        title = session_data.title if session_data else "New Chat"
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_sessions(self, user_id: str) -> List[ChatSession]:
        """Fetch all chat sessions for a user"""
        return self.db.query(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()).all()

    def get_session(self, session_id: UUID, user_id: str) -> ChatSession:
        """Fetch a single session, verifying ownership"""
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()
        if not session:
            raise NoResultFound(f"Chat session {session_id} not found for user {user_id}")
        return session

    # ---------- Chat Messages ----------
    def add_message(self, session_id: UUID, user_id: str, query: str, response: str, sources: list = None, chat_metadata: dict = None) -> ChatMessage:
        """Add a message to a chat session"""
        session = self.get_session(session_id, user_id)
    
        # Update title if still default
        if session.title == "New Chat" and query:
            session.title = query[:50]  # first 50 chars of first query
            self.db.add(session)

        message = ChatMessage(session_id=session_id, user_id=user_id, query=query, response=response, sources=sources or [], chat_metadata=chat_metadata or {})
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(self, session_id: UUID, user_id: str) -> List[ChatMessage]:
        """Fetch all messages in a session, verifying ownership"""
        session = self.get_session(session_id, user_id)
        return self.db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()

    # ---------- Composite ----------

    def get_session_with_messages(self, session_id: UUID, user_id: str) -> ChatSessionWithMessages:
        """Return session with all messages, for API response"""
        session = self.get_session(session_id, user_id)
        messages = self.get_messages(session_id, user_id)
        return ChatSessionWithMessages(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at,
            messages=messages
        )

    # ---------- Deletion ----------
    def delete_session(self, session_id: UUID, user_id: str):
        session = (
            self.db.query(ChatSession)
            .filter_by(id=session_id, user_id=user_id)
            .first()
        )
        if not session:
            raise BadRequestException("Chat session not found or access denied")

        # Delete session (cascade should remove messages if configured in models)
        self.db.delete(session)
        self.db.commit()
        return True
