from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


# ---------- Chat Session ----------

class ChatSessionBase(BaseModel):
    title: Optional[str] = "New Chat"


class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSessionUpdate(BaseModel):
    title: str
    
class ChatSessionResponse(ChatSessionBase):
    id: UUID
    user_id: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


# ---------- Chat Message ----------

class ChatMessageBase(BaseModel):
    query: str
    response: str
    # Store retrieval sources for traceability
    sources: List[Dict[str, Any]] = []
    # Extra metadata: could store embeddings, chunk refs, scoring, etc.
    chat_metadata: Dict[str, Any] = {}


class ChatMessageCreate(ChatMessageBase):
    session_id: UUID


class ChatMessageResponse(ChatMessageBase):
    id: UUID
    session_id: UUID
    user_id: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


# ---------- Composite ----------

class ChatSessionWithMessages(ChatSessionResponse):
    messages: List[ChatMessageResponse] = []
