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
from app.database import get_db
from app.config import settings
from app.core.dependencies import get_current_active_user
from app.core.exceptions import BadRequestException

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
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload multiple CSV/Excel files for MCP analysis"""
    try:
        user_id = current_user["sub"]
        data_processor = MCPDataProcessor(settings)
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
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files")
async def list_files(
    folder_id: Optional[str] = None,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List uploaded files for the current user"""
    try:
        user_id = current_user["sub"]
        tools = MCPTools(db, user_id)
        result = tools.list_files(folder_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/query")
async def query_data(
    request: QueryRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Process natural language data queries"""
    try:
        user_id = current_user["sub"]
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
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat history for a session"""
    try:
        user_id = current_user["sub"]
        tools = MCPTools(db, user_id)
        result = tools.get_chat_history(session_id, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")


@router.delete("/chat/{session_id}")
async def clear_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Clear chat history for a session"""
    try:
        user_id = current_user["sub"]
        tools = MCPTools(db, user_id)
        result = tools.clear_chat_history(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")


@router.get("/describe/{file_id}")
async def describe_file(
    file_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a file"""
    try:
        user_id = current_user["sub"]
        tools = MCPTools(db, user_id)
        result = tools.describe_file(file_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to describe file: {str(e)}")


@router.get("/columns/{file_id}")
async def get_columns(
    file_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get column names for a file"""
    try:
        user_id = current_user["sub"]
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
