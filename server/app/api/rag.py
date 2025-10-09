from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status , Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.schemas import RAGQuery, RAGResponse
from app.models import User as UserModel
from app.core.dependencies import get_current_active_user
from app.core.exceptions import BadRequestException, PermissionDeniedException
from app.services.rag_service import RAGService
from app.logger.logger import setup_logger
logger = setup_logger()

router = APIRouter()

@router.post("/query", response_model=RAGResponse)
async def rag_query(
    rag_query: RAGQuery,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit a RAG query and get an AI-generated response with sources"""
    logger.info(f"Received RAG query from user {current_user.user_id} on folder {rag_query.folder_ids}: {rag_query.query}")
    rag_service = RAGService(db)
    
    try:
        response = await rag_service.query(
            user_id=current_user.user_id,
            rag_query=rag_query
        )
        logger.info(f"RAG query processed successfully for user {current_user.user_id}: {response.answer[:100]}...")
        return response
    except (BadRequestException, PermissionDeniedException) as e:
        logger.warning(f"RAG query failed for user {current_user.user_id}: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"RAG query failed for user {current_user.user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/folders")
def get_queryable_folders(
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get list of folders that user can query"""
    logger.info(f"Getting queryable folders for user {current_user.user_id}")
    rag_service = RAGService(db)

    folders = rag_service.get_queryable_folders(current_user.user_id)
    logger.info(f"User {current_user.user_id} can query {len(folders)} folders namely: {[f['name'] for f in folders]}")
    return folders

@router.post("/suggest-queries")
async def suggest_related_queries(
    original_query: str,
    folder_ids: List[str] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, List[str]]:
    """Get suggested related queries based on available content"""
    logger.info(f"Suggesting related queries for user {current_user.user_id} based on query: {original_query} and folders: {folder_ids}")
    rag_service = RAGService(db)
    
    # Convert string UUIDs to UUID objects if provided
    folder_uuid_list = None
    if folder_ids:
        try:
            from uuid import UUID
            folder_uuid_list = [UUID(folder_id) for folder_id in folder_ids]
        except ValueError:
            logger.error(f"Invalid folder ID format in {folder_ids}")
            raise BadRequestException("Invalid folder ID format")
    
    suggestions = await rag_service.suggest_related_queries(
        user_id=current_user.user_id,
        original_query=original_query,
        folder_ids=folder_uuid_list
    )
    logger.info(f"Suggested {len(suggestions)} related queries for user {current_user.user_id} which are: {suggestions}")
    return {"suggestions": suggestions}

@router.get("/health")
def rag_health_check(
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Check RAG system health and user's access"""
    logger.info(f"Performing RAG health check for user {current_user.user_id}")
    rag_service = RAGService(db)
    
    # Get basic stats about user's accessible content
    queryable_folders = rag_service.get_queryable_folders(current_user.id)
    queryable_folders_names = [f["name"] for f in queryable_folders]
    logger.info(f"User {current_user.user_id} has access to {queryable_folders_names} folders for RAG queries")
    
    total_folders = len(queryable_folders)
    queryable_folders_count = len([f for f in queryable_folders if f["can_query"]])
    total_documents = sum(f["document_count"] for f in queryable_folders)
    total_embeddings = sum(f["embedding_count"] for f in queryable_folders)
    
    logger.info("RAG health check completed successfully. Status: healthy")
    return {
        "status": "healthy",
        "user_id": str(current_user.user_id),
        "accessible_folders": total_folders,
        "queryable_folders": queryable_folders_count,
        "total_documents": total_documents,
        "total_embeddings": total_embeddings,
        "can_query": queryable_folders_count > 0
    }