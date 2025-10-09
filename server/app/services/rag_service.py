import time
from typing import List, Dict, Any, Optional
from uuid import UUID
import openai
from sqlalchemy.orm import Session
from app.models import User
from app.config import settings
from app.core.exceptions import BadRequestException, PermissionDeniedException
from app.services.permission_service import PermissionService
from app.services.embedding_service import EmbeddingService
from app.services.chat_service import ChatService   
from app.schemas import RAGQuery, RAGResponse, RAGChunk, ChatMessageCreate
from app.logger.logger import setup_logger
logger = setup_logger()

class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        self.permission_service = PermissionService(db)
        self.embedding_service = EmbeddingService(db)
    
    async def query(
        self,
        user_id: str,
        rag_query: RAGQuery
    ) -> RAGResponse:
        """Process a RAG query and return response with sources"""
        logger.info(f"Processing RAG query for user {user_id}: {rag_query.query}")
        start_time = time.time()
        
        try:
            # Get accessible folders for the user
            accessible_folders = self._get_accessible_folders(user_id, rag_query.folder_ids)
            
            if not accessible_folders:
                logger.warning("No accessible folders found for query")
                raise PermissionDeniedException("No accessible folders found for query")
            
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embeddings([rag_query.query])[0]
            
            # Search for similar chunks
            similar_chunks = self.embedding_service.search_similar_chunks(
                query_embedding=query_embedding,
                folder_ids=accessible_folders,
                limit=rag_query.limit,
                min_similarity=rag_query.min_relevance_score
            )
            logger.info(f"Found {len(similar_chunks)} similar chunks for the query")
            # Initialize ChatService
            chat_service = ChatService(self.db)

            if not similar_chunks:
                chat_service.add_message(
                    session_id=rag_query.session_id,
                    user_id=user_id,
                    query=rag_query.query,
                    response="No relevant documents found for your query.",
                    sources=[]
                )
                logger.info(f"No relevant documents found for user {user_id} for query {rag_query.query}")
                return RAGResponse(
                    query=rag_query.query,
                    answer="No relevant documents found for your query.",
                    sources=[],
                    total_chunks=0,
                    processing_time=time.time() - start_time
                )
            
            # Generate answer using OpenAI
            answer = await self._generate_answer(rag_query.query, similar_chunks)
            logger.info(f"Generated answer for user {user_id} for query {rag_query.query}")
            # Format sources
            sources = []
            for chunk in similar_chunks:
                source = RAGChunk(
                    document_id=chunk["document_id"],
                    document_name=chunk["document_name"],
                    folder_id=chunk["folder_id"],
                    folder_name=chunk["folder_name"],
                    chunk_text=chunk["chunk_text"],
                    relevance_score=chunk["similarity_score"],
                    metadata=chunk["metadata"]
                )
                sources.append(source)
            logger.info(f"Gathered {len(sources)} sources for the answer")

            # ---------- Persist query/response to chat session ----------
            def serialize_source(source: RAGChunk):
                return {
                    "document_id": str(source.document_id),
                    "document_name": source.document_name,
                    "folder_id": str(source.folder_id),
                    "folder_name": source.folder_name,
                    "chunk_text": source.chunk_text,
                    "relevance_score": source.relevance_score,
                    "metadata": source.metadata
                }

            chat_service.add_message(
                session_id=rag_query.session_id,
                user_id=user_id,
                query=rag_query.query,
                response=answer,
                sources=[serialize_source(s) for s in sources]
            )
            logger.info(f"Chat message added for user {user_id} in session {rag_query.session_id}")
            processing_time = time.time() - start_time

            logger.info(f"RAG query processed in {processing_time:.2f} seconds for user {user_id}")
            return RAGResponse(
                query=rag_query.query,
                answer=answer,
                sources=sources,
                total_chunks=len(similar_chunks),
                processing_time=processing_time
            )
            
        except Exception as e:
            if isinstance(e, (BadRequestException, PermissionDeniedException)):
                logger.warning(f"RAG query failed due to client error: {str(e)}")
                raise
            logger.error(f"Failed to process RAG query: {str(e)}")
            raise BadRequestException(f"Failed to process RAG query: {str(e)}")
    
    def _get_accessible_folders(
        self,
        user_id: str,
        requested_folder_ids: Optional[List[UUID]] = None
    ) -> List[UUID]:
        """Get list of folder IDs that user can access"""
        logger.info(f"Fetching accessible folders for user {user_id}")
        # Get all accessible folders for user
        accessible_folders = self.permission_service.get_user_accessible_folders(user_id)
        accessible_folder_ids = [folder.id for folder in accessible_folders]
        
        # If specific folders were requested, filter to only include accessible ones
        if requested_folder_ids:
            filtered_folder_ids = []
            for folder_id in requested_folder_ids:
                if folder_id in accessible_folder_ids:
                    filtered_folder_ids.append(folder_id)
            logger.info(f"User {user_id} requested specific folders. Accessible folders after filtering: {filtered_folder_ids}")
            return filtered_folder_ids
        logger.info(f"User {user_id} has access to folders: {accessible_folder_ids}")        
        return accessible_folder_ids
    
    async def _generate_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]]
    ) -> str:
        """Generate answer using OpenAI with provided context"""
        logger.info(f"Generating answer for query using OpenAI")
        # Prepare context from chunks
        context_texts = []
        for chunk in context_chunks:
            context_texts.append(
                f"Document: {chunk['document_name']}\n"
                f"Content: {chunk['chunk_text']}\n"
                f"Relevance: {chunk['similarity_score']:.2f}\n"
            )
        
        context = "\n---\n".join(context_texts)
        
        # Create prompt
        system_prompt = """You are a helpful AI assistant that answers questions based on provided documents. 
Use only the information from the provided context to answer questions. 
If the context doesn't contain enough information to answer the question, say so clearly.
Cite the relevant documents when possible."""
        
        user_prompt = f"""Based on the following context documents, please answer this question: {query}

Context:
{context}

Answer:"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )

            logger.info(f"Generated answer for for query {query}: {response.choices[0].message.content.strip()}")
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate answer from OpenAI: {str(e)}")
            raise BadRequestException(f"Failed to generate answer: {str(e)}")
    
    def get_queryable_folders(self, user_id: str) -> List[Dict[str, Any]]:
        """Get list of folders that user can query"""
        logger.info(f"Fetching queryable folders for user {user_id}")
        accessible_folders = self.permission_service.get_user_accessible_folders(user_id)
        
        result = []
        for folder in accessible_folders:
            # Count documents in folder
            from app.models import Document
            document_count = self.db.query(Document).filter(
                Document.folder_id == folder.id
            ).count()
            logger.info(f"Folder {folder.id} has {document_count} documents")

            # Count embeddings in folder
            from app.models import Embedding
            embedding_count = self.db.query(Embedding).join(Document).filter(
                Document.folder_id == folder.id
            ).count()
            logger.info(f"Folder {folder.id} has {embedding_count} embeddings")

            result.append({
                "id": folder.id,
                "name": folder.name,
                "path": folder.path,
                "document_count": document_count,
                "embedding_count": embedding_count,
                "can_query": embedding_count > 0
            })
            logger.info(f"Folder info added for folder {folder.id}")        
        return result
    
    async def suggest_related_queries(
        self,
        user_id: str,
        original_query: str,
        folder_ids: Optional[List[UUID]] = None
    ) -> List[str]:
        """Suggest related queries based on available content"""
        logger.info(f"Suggesting related queries for user {user_id} based on original query: {original_query}")
        try:
            accessible_folders = self._get_accessible_folders(user_id, folder_ids)
            
            if not accessible_folders:
                logger.info(f"No accessible folders found for user {user_id}")
                return []
            
            # Get a sample of document titles and chunk texts for context
            from app.models import Document, Embedding
            
            # Get recent documents in accessible folders
            recent_docs = self.db.query(Document).filter(
                Document.folder_id.in_(accessible_folders)
            ).limit(10).all()
            logger.info(f"Found {len(recent_docs)} recent documents for user {user_id} in accessible folders")
            doc_titles = [doc.filename for doc in recent_docs]
            
            # Create prompt for suggesting related queries
            system_prompt = """You are a helpful assistant that suggests related questions based on available documents.
Generate 3-5 related questions that someone might ask about the given documents."""
            
            user_prompt = f"""Based on these available documents: {', '.join(doc_titles)}
And the original query: "{original_query}"

Suggest 3-5 related questions that someone might ask:"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            suggestions_text = response.choices[0].message.content.strip()
            
            # Parse suggestions (assuming they're in a numbered list)
            suggestions = []
            for line in suggestions_text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Remove numbering and clean up
                    suggestion = line.split('.', 1)[-1].strip()
                    suggestion = suggestion.lstrip('- ').strip()
                    if suggestion:
                        suggestions.append(suggestion)
            logger.info(f"Suggested related queries: {suggestions}")            
            return suggestions[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            logger.error(f"Failed to suggest related queries: {str(e)}")
            # Return empty list on error rather than failing
            return []