from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status , Response
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from app.database import get_db
from app.models import User as UserModel
from app.models.chat import ChatSession , ChatMessage
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionWithMessages,
    ChatSessionUpdate,
)
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException, PermissionDeniedException
from app.services.chat_service import ChatService
from app.logger.logger import setup_logger
logger = setup_logger()

router = APIRouter()


# ---------- Chat Sessions ----------

@router.post("/sessions", response_model=ChatSessionResponse)
def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session for the current user"""
    logger.info(f"Creating chat session for user: {current_user.user_id}, title: {session_data.title}")
    chat_service = ChatService(db)
    try:
        session = chat_service.create_session(current_user.user_id, session_data)
        logger.info(f"Chat session created successfully: {session.id}")
        return session
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_chat_sessions(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all chat sessions for the current user"""
    logger.info(f"Listing chat sessions for user: {current_user.user_id}")
    chat_service = ChatService(db)
    try:
        sessions = chat_service.get_sessions(current_user.user_id)
        logger.info(f"Fetched {len(sessions)} chat sessions for user: {current_user.user_id}")
        return sessions
    except Exception as e:
        logger.error(f"Error listing chat sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat sessions: {str(e)}"
        )


# ---------- Chat Messages ----------

@router.post("/{session_id}/messages", response_model=ChatMessageResponse)
def add_chat_message(
    session_id: UUID,
    message_data: ChatMessageCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new message to an existing chat session"""
    logger.info(f"Adding chat message to session {session_id} for user {current_user.user_id}")
    chat_service = ChatService(db)
    try:
        # Verify session ownership
        chat_service.get_session(session_id, current_user.user_id)
        message = chat_service.add_message(
            session_id=session_id,
            user_id=current_user.user_id,
            query=message_data.query,
            response=message_data.response,
            sources=message_data.sources,
            chat_metadata=message_data.chat_metadata
        )
        logger.info(f"Chat message added: {message.id} successfully to session {session_id}")
        return message
    except BadRequestException as e:
        logger.warning(f"Bad request when adding message to session {session_id}: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error adding chat message to session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add chat message: {str(e)}"
        )


@router.get("/{session_id}/messages", response_model=ChatSessionWithMessages)
def get_chat_messages(
    session_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch all messages for a chat session"""
    logger.info(f"Fetching messages for session {session_id} for user {current_user.user_id}")
    chat_service = ChatService(db)
    try:
        session_with_messages = chat_service.get_session_with_messages(session_id, current_user.user_id)
        logger.info(f"Retrieved {len(session_with_messages.messages)} messages for session {session_id}")
        return session_with_messages
    except BadRequestException as e:
        logger.warning(f"Bad request when fetching messages for session {session_id}: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error fetching messages for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat messages: {str(e)}"
        )

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific chat session (and its messages) for the current user"""
    logger.info(f"Deleting chat session {session_id} for user {current_user.user_id}")
    chat_service = ChatService(db)
    try:
        # Verify ownership
        logger.info(f"Fetching session {session_id} for user {current_user.user_id}")
        chat_service.get_session(session_id, current_user.user_id)

        # Delete session
        logger.info(f"Deleting chat session {session_id}")
        chat_service.delete_session(session_id, current_user.user_id)
        
        logger.info(f"Chat session {session_id} and its messages deleted for user {current_user.user_id}")
        # Return 204 properly (no body)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except BadRequestException as e:
        logger.warning(f"Bad request when deleting chat session {session_id}: {str(e)}")
        raise e
    except PermissionDeniedException as e:
        logger.warning(f"Permission denied when deleting chat session {session_id}: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error deleting chat session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat session: {str(e)}"
        )

@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_chat_session(
    session_id: UUID,
    payload: ChatSessionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logger.info(f"Updating chat session {session_id} for user {current_user.user_id}, new title: {payload.title}")
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.user_id)
        .first()
    )
    if not session:
        logger.warning(f"Chat session {session_id} not found for user {current_user.user_id}")
        raise HTTPException(status_code=404, detail="Chat session not found")

    session.title = payload.title
    db.commit()
    db.refresh(session)
    logger.info(f"Chat session {session_id} updated successfully")
    return session