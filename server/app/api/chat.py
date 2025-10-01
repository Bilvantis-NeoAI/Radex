from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status , Response
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from app.database import get_db
from app.models import User as UserModel
from app.models import OktaUser
from app.models.chat import ChatSession , ChatMessage
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionWithMessages,
    ChatSessionUpdate,
)
from app.core.dependencies import get_current_okta_user
from app.core.exceptions import BadRequestException, PermissionDeniedException
from app.services.chat_service import ChatService

router = APIRouter()


# ---------- Chat Sessions ----------

@router.post("/sessions", response_model=ChatSessionResponse)
def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: OktaUser = Depends(get_current_okta_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session for the current user"""
    chat_service = ChatService(db)
    try:
        session = chat_service.create_session(current_user.okta_user_id, session_data)
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_chat_sessions(
    current_user: OktaUser = Depends(get_current_okta_user),
    db: Session = Depends(get_db)
):
    """List all chat sessions for the current user"""
    chat_service = ChatService(db)
    try:
        sessions = chat_service.get_sessions(current_user.okta_user_id)
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat sessions: {str(e)}"
        )


# ---------- Chat Messages ----------

@router.post("/{session_id}/messages", response_model=ChatMessageResponse)
def add_chat_message(
    session_id: UUID,
    message_data: ChatMessageCreate,
    current_user: OktaUser = Depends(get_current_okta_user),
    db: Session = Depends(get_db)
):
    """Add a new message to an existing chat session"""
    chat_service = ChatService(db)
    try:
        # Verify session ownership
        chat_service.get_session(session_id, current_user.okta_user_id)
        message = chat_service.add_message(
            session_id=session_id,
            user_id=current_user.okta_user_id,
            query=message_data.query,
            response=message_data.response,
            sources=message_data.sources,
            chat_metadata=message_data.chat_metadata
        )
        return message
    except BadRequestException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add chat message: {str(e)}"
        )


@router.get("/{session_id}/messages", response_model=ChatSessionWithMessages)
def get_chat_messages(
    session_id: UUID,
    current_user: OktaUser = Depends(get_current_okta_user),
    db: Session = Depends(get_db)
):
    """Fetch all messages for a chat session"""
    chat_service = ChatService(db)
    try:
        session_with_messages = chat_service.get_session_with_messages(session_id, current_user.okta_user_id)
        return session_with_messages
    except BadRequestException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat messages: {str(e)}"
        )

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: UUID,
    current_user: OktaUser = Depends(get_current_okta_user),
    db: Session = Depends(get_db)
):
    """Delete a specific chat session (and its messages) for the current user"""
    chat_service = ChatService(db)
    try:
        # Verify ownership
        print("Trying to get session", session_id, "for user", current_user.okta_user_id)
        chat_service.get_session(session_id, current_user.okta_user_id)

        # Delete session
        print("Deleting session", session_id)
        chat_service.delete_session(session_id, current_user.okta_user_id)
        
        # Return 204 properly (no body)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except BadRequestException as e:
        raise e
    except PermissionDeniedException as e:
        raise e
    except Exception as e:
        print("Error deleting session:", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat session: {str(e)}"
        )

@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_chat_session(
    session_id: UUID,
    payload: ChatSessionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_okta_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.okta_user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    session.title = payload.title
    db.commit()
    db.refresh(session)
    return session