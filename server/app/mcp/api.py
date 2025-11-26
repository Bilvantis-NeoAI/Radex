"""
API Router for MCP Module

FastAPI routers for MCP data analysis endpoints
integrated with RADEX authentication and error handling.
"""

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid


from app.mcp.data_processor import MCPDataProcessor
from app.mcp.chat_manager import MCPChatManager
from app.mcp.tools import MCPTools
from app.models.mcp import McpFileMetadata, McpQueryHistory, McpChatSession
import json
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.config import settings
from app.core.dependencies import get_current_active_user
from app.core.exceptions import BadRequestException
from app.models import User


router = APIRouter()

class QueryRequest(BaseModel):
    question: str
    session_id: str
    folder_id: Optional[str] = None


@router.get("/health")
async def mcp_health():
    """MCP module health check"""
    return {"status": "healthy", "module": "MCP Data Analysis"}


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    folder_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload multiple CSV/Excel files for MCP analysis"""
    try:
        user_id = str(current_user.id)
        data_processor = MCPDataProcessor(db, settings)
        chat_manager = MCPChatManager(db)

        # Create session if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            chat_manager.create_session(user_id, session_id)

        uploaded_files = []
        for file in files:
            # Validate file type
            if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not a supported format. Only CSV and Excel files are allowed."
                )

            # Read file content
            content = await file.read()

            # Upload via data processor
            result = await data_processor.upload_file(
                file_data=content,
                filename=file.filename,
                folder_id=folder_id,
                user_id=user_id
            )

            uploaded_files.append(result)

        return {
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "uploaded_files": uploaded_files,
            "session_id": session_id
        }

    except Exception as e:
        print(f"DEBUG MCP: Final upload failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files")
async def list_files(
    folder_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List uploaded files for the current user"""
    try:
        user_id = str(current_user.id)
        tools = MCPTools(db, user_id)
        result = tools.list_files(folder_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/query")
async def query_data(
    request: QueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Process natural language data queries"""
    try:
        user_id = str(current_user.id)
        tools = MCPTools(db, user_id)

        # Get available files
        available_files = tools.data_processor.list_user_files(user_id, request.folder_id)
        if not available_files:
            return {
                "response": "No files uploaded yet. Please upload some CSV/Excel files first.",
                "type": "no_data"
            }

        # Get recent chat history for context
        chat_history = tools.get_chat_history(request.session_id)["history"]

        # Generate AI-powered response
        result = tools.generate_ai_response(
            question=request.question,
            available_files=available_files,
            session_id=request.session_id,
            chat_history=chat_history
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/chat/{session_id}")
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat history for a session"""
    try:
        user_id = str(current_user.id)
        tools = MCPTools(db, user_id)
        result = tools.get_chat_history(session_id, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")


@router.delete("/chat/{session_id}")
async def clear_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Clear chat history for a session"""
    try:
        user_id = str(current_user.id)
        tools = MCPTools(db, user_id)
        result = tools.clear_chat_history(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")


@router.get("/describe/{file_id}")
async def describe_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a file"""
    try:
        user_id = str(current_user.id)
        tools = MCPTools(db, user_id)
        result = tools.describe_file(file_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to describe file: {str(e)}")


@router.get("/columns/{file_id}")
async def get_columns(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get column names for a file"""
    try:
        user_id = str(current_user.id)
        tools = MCPTools(db, user_id)
        result = tools.get_columns(file_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get columns: {str(e)}")


@router.get("/tools")
async def list_tools():
    """List available MCP tools (for API documentation)"""
    return {
        "tools": [
            {
                "name": "upload_files",
                "description": "Upload CSV/Excel files for analysis",
                "endpoint": "/upload"
            },
            {
                "name": "list_files",
                "description": "List uploaded files",
                "endpoint": "/files"
            },
            {
                "name": "query_data",
                "description": "Process natural language queries",
                "endpoint": "/query"
            },
            {
                "name": "describe_file",
                "description": "Get file information and statistics",
                "endpoint": "/describe/{file_id}"
            },
            {
                "name": "get_columns",
                "description": "Get column names for a file",
                "endpoint": "/columns/{file_id}"
            }
        ]
    }


    @router.get("/resources")
    async def list_resources(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """List MCP resources (uploaded CSV/Excel files) for the current user"""
        try:
            user_id = str(current_user.id)
            data_processor = MCPDataProcessor(db, settings)
            files = await data_processor.list_user_files(user_id)

            resources = []
            for f in files:
                resources.append({
                    "uri": f"mcp://{f['file_id']}",
                    "name": f['filename'],
                    "description": f"MCP file: {f['filename']}",
                    "mimeType": "application/octet-stream",
                    "metadata": {
                        "file_size": f.get('file_size', 0),
                        "row_count": f.get('row_count', 0),
                        "upload_time": f.get('upload_time', 0),
                        "columns": f.get('columns', [])
                    }
                })

            return {"resources": resources}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list resources: {str(e)}")


    @router.get("/source/{query_id}")
    async def get_source_info(
        query_id: str,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Retrieve saved source information for a specific query_id within the user's sessions"""
        try:
            user_id = str(current_user.id)

            # Get user's sessions
            sessions = db.query(McpChatSession).filter(McpChatSession.user_id == user_id).all()
            session_ids = [s.session_id for s in sessions]

            # Search query histories for a matching query_id inside the source_info JSON
            matches = []
            histories = db.query(McpQueryHistory).filter(McpQueryHistory.session_id.in_(session_ids)).all()
            for h in histories:
                si = h.source_info or {}
                try:
                    if isinstance(si, str):
                        si = json.loads(si)
                except Exception:
                    si = {}

                if isinstance(si, dict) and si.get('query_id') == query_id:
                    matches.append({
                        "session_id": h.session_id,
                        "question": h.question,
                        "response": h.response,
                        "source_info": si,
                        "timestamp": h.created_at.isoformat()
                    })

            if not matches:
                raise NotFoundException("Source information not found")

            return {"query_id": query_id, "matches": matches}
        except NotFoundException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve source info: {str(e)}")


class AssistantQueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    folder_id: Optional[str] = None


@router.post("/assistant/query")
async def assistant_query(
    payload: AssistantQueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Unified assistant endpoint: routes to MCP for CSV/Excel analysis or RAG for other documents.

    Local imports are used to avoid circular-import issues during module import time.
    """
    try:
        # Local imports to avoid circular dependencies at module import time
        from uuid import UUID
        from app.services.rag_service import RAGService
        from app.schemas.rag import ChatRequest, ChatMessage

        user_id = str(current_user.id)

        # Build folder list: if folder_id provided, use it; otherwise use all accessible folders
        folder_ids = []
        if payload.folder_id:
            try:
                folder_ids = [UUID(payload.folder_id)]
            except Exception:
                raise BadRequestException("Invalid folder_id format")
        else:
            # Use RAGService to get accessible folders
            rag_service = RAGService(db)
            folders = rag_service.get_queryable_folders(current_user.id)
            folder_ids = [f['id'] for f in folders]

        if not folder_ids:
            raise BadRequestException("No accessible folders found for user")

        # Construct chat request with single user message
        chat_req = ChatRequest(
            messages=[ChatMessage(role="user", content=payload.question)],
            folder_ids=folder_ids,
            limit=10,
            min_relevance_score=0.7
        )

        rag_service = RAGService(db)
        # RAGService.chat will internally detect CSV/Excel questions and call MCP as needed
        response = await rag_service.chat(user_id=current_user.id, chat_request=chat_req)

        return response
    except BadRequestException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant query failed: {str(e)}")
