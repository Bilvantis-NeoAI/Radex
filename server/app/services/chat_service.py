from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate, ChatSessionWithMessages
from app.core.exceptions import BadRequestException
from app.logger.logger import setup_logger
logger = setup_logger()

class ChatService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- Chat Sessions ----------

    def create_session(self, user_id: str, session_data: ChatSessionCreate = None) -> ChatSession:
        """Create a new chat session for the user"""
        logger.info(f"Creating chat session for user: {user_id}")
        title = session_data.title if session_data else "New Chat"
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info(f"Chat session created with ID: {session.id} for user: {user_id}")
        return session

    def get_sessions(self, user_id: str) -> List[ChatSession]:
        """Fetch all chat sessions for a user"""
        logger.info(f"Fetching chat sessions for user: {user_id}")
        sessions = self.db.query(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()).all()
        logger.info(f"Found {len(sessions)} chat sessions for user: {user_id}")
        return sessions

    def get_session(self, session_id: UUID, user_id: str) -> ChatSession:
        """Fetch a single session, verifying ownership"""
        logger.info(f"Fetching information of chat session: {session_id} for user: {user_id}")
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()
        if not session:
            logger.warning(f"Chat session {session_id} not found")
            raise NoResultFound(f"Chat session {session_id} not found for user {user_id}")
        return session

    # ---------- Chat Messages ----------
    def add_message(self, session_id: UUID, user_id: str, query: str, response: str, sources: list = None, chat_metadata: dict = None) -> ChatMessage:
        """Add a message to a chat session"""
        logger.info(f"Adding message to chat session: {session_id} for user: {user_id}")
        session = self.get_session(session_id, user_id)
    
        # Update title if still default
        if session.title == "New Chat" and query:
            logger.info(f"Updating title of chat session: {session_id} for user: {user_id}")
            session.title = query[:50]  # first 50 chars of first query
            self.db.add(session)

        message = ChatMessage(session_id=session_id, user_id=user_id, query=query, response=response, sources=sources or [], chat_metadata=chat_metadata or {})
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        logger.info(f"Message added to chat session: {session_id} with message ID: {message.id}")
        return message

    def get_messages(self, session_id: UUID, user_id: str) -> List[ChatMessage]:
        """Fetch all messages in a session, verifying ownership"""
        logger.info(f"Fetching messages for chat session: {session_id} for user: {user_id}")
        session = self.get_session(session_id, user_id)
        messages = self.db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()
        logger.info(f"Found {len(messages)} messages for chat session: {session_id}")
        return messages

    # ---------- Composite ----------

    def get_session_with_messages(self, session_id: UUID, user_id: str) -> ChatSessionWithMessages:
        """Return session with all messages, for API response"""
        logger.info(f"Fetching session with messages for chat session: {session_id} for user: {user_id}")
        session = self.get_session(session_id, user_id)
        messages = self.get_messages(session_id, user_id)
        logger.info(f"Returning session with {len(messages)} messages for chat session: {session_id}")
        return ChatSessionWithMessages(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at,
            messages=messages
        )

    # ---------- Deletion ----------
    def delete_session(self, session_id: UUID, user_id: str):
        """Delete a chat session and all its messages"""
        logger.info(f"Deleting chat session: {session_id} for user: {user_id}")
        session = (
            self.db.query(ChatSession)
            .filter_by(id=session_id, user_id=user_id)
            .first()
        )
        if not session:
            logger.warning(f"Chat session {session_id} not found or access denied for user: {user_id}")
            raise BadRequestException("Chat session not found or access denied")

        # Delete session (cascade should remove messages if configured in models)
        self.db.delete(session)
        self.db.commit()
        logger.info(f"Chat session {session_id} deleted successfully for user: {user_id}")
        return True
