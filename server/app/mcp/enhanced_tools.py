"""
Enhanced MCP Tools for Data Analysis

Integrates the enhanced CSV/Excel processing capabilities from MCP_POC
with RADEX's existing authentication and storage systems.
"""

import openai
import json
import uuid
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.mcp.data_processor import MCPDataProcessor
from app.mcp.chat_manager import MCPChatManager
from app.config import settings
from app.core.exceptions import BadRequestException, PermissionDeniedException
from app.models.mcp import McpFileMetadata

class EnhancedMCPTools:
    """Enhanced MCP data analysis tools with advanced features"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.data_processor = MCPDataProcessor(settings, db)
        self.chat_manager = MCPChatManager(db)
        self.source_tracking = {}  # query_id -> source information
        self.file_metadata = {}  # file_id -> metadata
        self.df_cache = {}  # file_id -> (df, timestamp)
        self.CACHE_TIMEOUT = 300  # 5 minutes

    def list_available_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools with proper schemas"""
        return [
            {
                "name": "list_files",
                "description": "List all uploaded CSV/Excel files with their columns and metadata",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "folder_id": {"type": "string", "description": "Optional folder ID to filter files"}
                    }
                }
            },
            {
                "name": "get_columns",
                "description": "Return all column names for a given file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string", "description": "File ID to get columns from"}
                    },
                    "required": ["file_id"]
                }
            },
            {
                "name": "describe_file",
                "description": "Provide detailed statistics and information about a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string", "description": "File ID to describe"}
                    },
                    "required": ["file_id"]
                }
            },
            {
                "name": "query_data",
                "description": "Perform queries on data using pandas operations with source tracking",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string", "description": "File ID to query"},
                        "operation": {"type": "string", "description": "Operation to perform (head, average, sum, count, describe, groupby_count, groupby_sum, groupby_max, groupby_min, value_counts, unique_values)"},
                        "column": {"type": "string", "description": "Column name for operations"},
                        "groupby_column": {"type": "string", "description": "Column to group by"},
                        "value_column": {"type": "string", "description": "Column to aggregate (for groupby operations)"},
                        "n": {"type": "integer", "description": "Number of rows for head operation"},
                        "limit": {"type": "integer", "description": "Limit results for groupby operations"},
                        "filter": {"type": "string", "description": "Pandas filter expression"},
                        "code": {"type": "string", "description": "Pandas code for execute operation"},
                        "session_id": {"type": "string", "description": "Chat session ID"},
                        "question": {"type": "string", "description": "Natural language question"},
                        "query_id": {"type": "string", "description": "Query tracking ID"}
                    },
                    "required": ["file_id", "operation"]
                }
            },
            {
                "name": "get_chat_history",
                "description": "Get chat history for a specific session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session ID to get history for"},
                        "limit": {"type": "integer", "description": "Maximum number of entries to return"}
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "get_source_info",
                "description": "Get detailed source information for a specific query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query_id": {"type": "string", "description": "Query ID to get source info for"}
                    },
                    "required": ["query_id"]
                }
            },
            {
                "name": "natural_language_query",
                "description": "Ask natural language questions about CSV/Excel data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Natural language question"},
                        "session_id": {"type": "string", "description": "Chat session ID"},
                        "available_files": {"type": "array", "description": "Available files context"},
                        "chat_history": {"type": "array", "description": "Recent chat history"}
                    },
                    "required": ["question", "session_id"]
                }
            }
        ]

    async def list_files(self, folder_id: Optional[str] = None) -> Dict[str, Any]:
        """List uploaded files with enhanced metadata"""
        try:
            files = await self.data_processor.list_user_files(self.user_id, folder_id)
            
            # Enhance file info with additional metadata
            enhanced_files = []
            for file_info in files:
                file_id = file_info['file_id']
                
                # Get database metadata
                db_file = self.db.query(McpFileMetadata).filter(
                    McpFileMetadata.file_id == file_id
                ).first()
                
                enhanced_file = {
                    **file_info,
                    "upload_time": db_file.upload_time.timestamp() if db_file else time.time(),
                    "last_accessed": db_file.last_accessed.timestamp() if db_file and db_file.last_accessed else None,
                    "file_type": db_file.file_type if db_file else "unknown",
                    "cache_status": "active" if file_id in self.df_cache else "not_cached"
                }
                enhanced_files.append(enhanced_file)
                
                # Update file metadata cache
                self.file_metadata[file_id] = enhanced_file

            # Generate query ID for source tracking
            query_id = str(uuid.uuid4())
            self._track_query_source(query_id, folder_id, "list_files", enhanced_files)

            return {
                "files": enhanced_files,
                "count": len(enhanced_files),
                "query_id": query_id,
                "source_info": {
                    "query_id": query_id,
                    "operation": "list_files",
                    "folder_id": folder_id,
                    "files_found": len(enhanced_files),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error listing files: {str(e)}")

    async def describe_file(self, file_id: str) -> Dict[str, Any]:
        """Get detailed information about a file with enhanced metadata"""
        # Verify ownership
        if not self._verify_file_ownership(file_id):
            raise PermissionDeniedException("Access denied to this file")

        try:
            description = await self.data_processor.describe_file(file_id)
            
            # Get database metadata
            db_file = self.db.query(McpFileMetadata).filter(
                McpFileMetadata.file_id == file_id
            ).first()
            
            enhanced_description = {
                "file_id": file_id,
                "filename": db_file.filename if db_file else "unknown",
                "upload_time": db_file.upload_time.timestamp() if db_file else None,
                "file_size": db_file.file_size if db_file else 0,
                "file_type": db_file.file_type if db_file else "unknown",
                "row_count": db_file.row_count if db_file else description.get("row_count", 0),
                "column_count": db_file.columns and len(db_file.columns) or description.get("column_count", 0),
                "columns": description.get("columns", []),
                "memory_usage": description.get("memory_usage", 0),
                "dtypes_summary": description.get("dtypes_summary", {})
            }
            
            # Generate query ID for source tracking
            query_id = str(uuid.uuid4())
            self._track_query_source(query_id, file_id, "describe_file", [enhanced_description])

            return {
                "description": enhanced_description,
                "query_id": query_id,
                "source_info": {
                    "query_id": query_id,
                    "operation": "describe_file",
                    "file_id": file_id,
                    "columns_analyzed": len(enhanced_description["columns"]),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error describing file: {str(e)}")

    async def get_columns(self, file_id: str) -> Dict[str, Any]:
        """Get column names for a file with enhanced metadata"""
        # Verify ownership
        if not self._verify_file_ownership(file_id):
            raise PermissionDeniedException("Access denied to this file")

        try:
            columns = await self.data_processor.get_columns(file_id)
            
            # Generate query ID for source tracking
            query_id = str(uuid.uuid4())
            self._track_query_source(query_id, file_id, "get_columns", columns)

            return {
                "file_id": file_id,
                "columns": columns,
                "column_count": len(columns),
                "query_id": query_id,
                "source_info": {
                    "query_id": query_id,
                    "operation": "get_columns",
                    "file_id": file_id,
                    "columns_returned": len(columns),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error getting columns: {str(e)}")

    async def query_data(self, file_id: str, operation: str, session_id: Optional[str] = None,
                        question: Optional[str] = None, query_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Execute pandas operations with comprehensive source tracking"""
        # Verify ownership
        if not self._verify_file_ownership(file_id):
            raise PermissionDeniedException("Access denied to this file")

        try:
            # Use provided query_id or generate new one
            if not query_id:
                query_id = str(uuid.uuid4())

            # Execute the query
            result = await self.data_processor.execute_query(file_id, operation, **kwargs)

            # Track source information
            columns_used = [kwargs.get('column')] if kwargs.get('column') else []
            self._track_query_source(query_id, file_id, operation, columns_used, result)

            # Update source tracking with query result summary
            if query_id in self.source_tracking:
                self.source_tracking[query_id]['query_result_summary'] = {
                    'result_type': type(result).__name__,
                    'result_size': len(str(result)) if result else 0,
                    'operation_specific': self._get_operation_summary(operation, result, kwargs)
                }

            # Save to chat history if provided
            if session_id and question:
                response_text = self._format_response_for_history(result)
                source_info = self.source_tracking.get(query_id, {})
                self.chat_manager.save_query(
                    session_id, question, response_text, source_info, query_id=query_id
                )

            return {
                "file_id": file_id,
                "operation": operation,
                "result": result,
                "query_id": query_id,
                "source_info": {
                    "query_id": query_id,
                    "operation": operation,
                    "file_id": file_id,
                    "columns_used": columns_used,
                    "result_type": type(result).__name__,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error executing query: {str(e)}")

    async def natural_language_query(self, question: str, available_files: List[Dict],
                                   session_id: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Process natural language queries about CSV/Excel data with AI assistance"""

        try:
            # Build context with available files and columns
            files_context = "\n".join([
                f"- {f['filename']}: columns {', '.join(f['columns'][:5])}{'...' if len(f['columns']) > 5 else ''}\n  Rows: {f['row_count']:,}"
                for f in available_files
            ])

            # Build chat history context
            history_context = ""
            if chat_history:
                recent = chat_history[-3:]  # Last 3 interactions
                history_context = "\nRecent Conversation:\n" + "\n".join([
                    f"Q: {entry['question']}\nA: {entry['response'][:150]}{'...' if len(entry['response']) > 150 else ''}"
                    for entry in recent
                ])

            # Use OpenAI to understand the question and determine approach
            client = openai.OpenAI(api_key=settings.openai_api_key)

            context = f"""{history_context}
Available Data Files:
{files_context}

Question: {question}

Analyze this question and determine if it can be answered using pandas operations on the available data files.

Common analytical patterns:
- "Who won the most X?" → groupby_max with groupby_column="player/participant" and value_column="X_count/awards"
- "What is the total X by Y?" → groupby_sum with groupby_column="Y" and value_column="X"
- "How many X does each Y have?" → groupby_count with groupby_column="Y"
- "Show top/bottom performers" → groupby operations with limit parameter

If answerable, respond with ONLY valid JSON:
{{
  "can_answer": true,
  "tool": "query_data",
  "reasoning": "brief explanation",
  "parameters": {{
    "file_id": "specific_file_id_from_available_files",
    "operation": "operation_name",
    "kwargs": {{"groupby_column": "group_column", "value_column": "value_column", "limit": 5}},
    "question": "{question}"
  }}
}}

If not answerable, respond with:
{{
  "can_answer": false,
  "reasoning": "brief explanation why not answerable"
}}

Available Operations:
- head: show first N rows
- average: column average
- sum: column sum
- count: total rows
- describe: statistics summary
- groupby_count: count by group
- groupby_sum: sum values by group
- groupby_max: find maximum by group (perfect for "most" queries)
- groupby_min: find minimum by group (for "least" queries)
- value_counts: frequency count for a column
- unique_values: get unique values from a column
- execute: custom pandas code"""

            response = client.chat.completions.create(
                model=settings.openai_chat_model or "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You analyze data questions and generate pandas operations. Respond ONLY with valid JSON."},
                    {"role": "user", "content": context}
                ],
                temperature=0.1,
                max_tokens=300
            )

            ai_response = response.choices[0].message.content.strip()

            # Clean up response
            if ai_response.startswith("```"):
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
                ai_response = ai_response.strip()

            result = json.loads(ai_response)

            if result.get("can_answer"):
                # Execute the determined query
                params = result["parameters"]
                query_result = await self.query_data(
                    file_id=params["file_id"],
                    operation=params["operation"],
                    session_id=session_id,
                    question=question,
                    **params.get("kwargs", {})
                )
                
                return {
                    "response": f"Based on the analysis: {result.get('reasoning', 'Analysis complete')}",
                    "tool_executed": True,
                    "query_result": query_result,
                    "source_info": query_result.get("source_info", {})
                }
            else:
                # Generate helpful response about limitations
                polite_response = await self._generate_helpful_response(question, available_files, result.get("reasoning", ""))

                return {
                    "response": polite_response,
                    "tool_executed": False,
                    "reasoning": result.get("reasoning", ""),
                    "source_info": {
                        "classification": "not_answerable",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

        except Exception as e:
            raise BadRequestException(f"Error processing natural language query: {str(e)}")

    def get_source_info(self, query_id: str) -> Dict[str, Any]:
        """Get detailed source information for a specific query"""
        source_info = self.source_tracking.get(query_id)
        if source_info:
            return {
                "query_id": query_id,
                "source_info": source_info
            }
        raise BadRequestException("Source information not found")

    def get_chat_history(self, session_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get chat history for a session"""
        try:
            history = self.chat_manager.get_chat_history(session_id, limit)
            return {
                "session_id": session_id,
                "history": history,
                "count": len(history)
            }
        except Exception as e:
            raise BadRequestException(f"Error retrieving chat history: {str(e)}")

    def clear_chat_history(self, session_id: str) -> Dict[str, Any]:
        """Clear chat history for a session"""
        try:
            success = self.chat_manager.clear_session_history(session_id)
            return {
                "success": success,
                "session_id": session_id,
                "message": "Chat history cleared" if success else "Failed to clear history"
            }
        except Exception as e:
            raise BadRequestException(f"Error clearing chat history: {str(e)}")

    # Helper methods
    def _verify_file_ownership(self, file_id: str) -> bool:
        """Verify that the user owns the file"""
        return file_id.startswith(f"{self.user_id}_")

    def _track_query_source(self, query_id: str, target: str, operation: str, 
                          data: Any = None, result: Any = None):
        """Track source information for a query"""
        self.source_tracking[query_id] = {
            "timestamp": datetime.utcnow().isoformat(),
            "target": target,  # file_id or folder_id
            "operation": operation,
            "data_accessed": data,
            "query_result_summary": None
        }

    def _get_operation_summary(self, operation: str, result: Any, kwargs: Dict) -> Dict[str, Any]:
        """Get operation-specific summary information"""
        if operation == "head":
            return {"rows_returned": len(result) if isinstance(result, list) else 0}
        elif operation in ["average", "sum"]:
            return {"column": kwargs.get("column"), "value": result}
        elif operation == "count":
            return {"total_rows": result}
        elif operation == "describe":
            return {"stats_computed": list(result.keys()) if isinstance(result, dict) else []}
        else:
            return {"operation": operation}

    def _format_response_for_history(self, result: Any) -> str:
        """Format result for chat history storage"""
        try:
            if isinstance(result, (list, dict)):
                return json.dumps(result)[:500] + ("..." if len(str(result)) > 500 else "")
            else:
                return str(result)[:500]
        except:
            return str(result)[:200]

    async def _generate_helpful_response(self, question: str, available_files: List[Dict], reasoning: str) -> str:
        """Generate helpful response when question can't be answered"""

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)

            files_info = "\n".join([
                f"- {f['filename']} ({f['row_count']:,} rows, columns: {', '.join(f['columns'][:4])}{'...' if len(f['columns']) > 4 else ''})"
                for f in available_files
            ])

            context = f"""User asked: "{question}"

Reason this couldn't be answered: {reasoning}

Available uploaded files:
{files_info}

Please provide a helpful, polite response explaining the limitation and suggest specific types of questions that can be asked about the available data. Make it conversational and encouraging."""

            response = client.chat.completions.create(
                model=settings.openai_chat_model or "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Be helpful, polite, and encouraging. Explain limitations clearly and suggest concrete alternatives."},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                max_tokens=200
            )

            return response.choices[0].message.content

        except Exception:
            return f"I'm sorry, but I couldn't find information to answer your question about '{question}' in the uploaded files. Please try asking about specific columns or data statistics from your CSV/Excel files!"
