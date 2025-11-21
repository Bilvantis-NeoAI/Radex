"""
MCP Tools for Data Analysis

Exposes pandas operations and natural language queries as tools
integrated with RADEX's authentication and storage systems.
"""

import openai
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.mcp.data_processor import MCPDataProcessor
from app.mcp.chat_manager import MCPChatManager
from app.config import settings
from app.core.exceptions import BadRequestException, PermissionDeniedException

class MCPTools:
    """MCP data analysis tools integrated with RADEX"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.data_processor = MCPDataProcessor(settings)
        self.chat_manager = MCPChatManager(db)

    def list_files(self, folder_id: str = None) -> Dict[str, Any]:
        """List uploaded files for the current user"""
        try:
            files = self.data_processor.list_user_files(self.user_id, folder_id)
            return {
                "files": files,
                "count": len(files),
                "source_info": {
                    "operation": "list_files",
                    "user_id": self.user_id,
                    "folder_id": folder_id
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error listing files: {str(e)}")

    def describe_file(self, file_id: str) -> Dict[str, Any]:
        """Get detailed information about a file"""
        # Verify ownership
        if not file_id.startswith(f"{self.user_id}_"):
            raise PermissionDeniedException("Access denied to this file")

        try:
            description = self.data_processor.describe_file(file_id)
            return {
                "file_id": file_id,
                **description,
                "source_info": {
                    "operation": "describe_file",
                    "file_id": file_id,
                    "user_id": self.user_id
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error describing file: {str(e)}")

    def get_columns(self, file_id: str) -> Dict[str, Any]:
        """Get column names for a file"""
        # Verify ownership
        if not file_id.startswith(f"{self.user_id}_"):
            raise PermissionDeniedException("Access denied to this file")

        try:
            columns = self.data_processor.get_columns(file_id)
            return {
                "file_id": file_id,
                "columns": columns,
                "column_count": len(columns),
                "source_info": {
                    "operation": "get_columns",
                    "file_id": file_id,
                    "columns_returned": len(columns)
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error getting columns: {str(e)}")

    def query_data(self, file_id: str, operation: str, session_id: str,
                   question: str = None, **kwargs) -> Dict[str, Any]:
        """Execute pandas operations on data"""
        # Verify ownership
        if not file_id.startswith(f"{self.user_id}_"):
            raise PermissionDeniedException("Access denied to this file")

        try:
            result = self.data_processor.execute_query(file_id, operation, **kwargs)

            # Save to chat history if provided
            if session_id and question:
                response_text = json.dumps(result)[:500]  # Truncate for storage
                source_info = {
                    "operation": operation,
                    "file_id": file_id,
                    "columns_used": kwargs.get('column'),
                    "result_type": type(result).__name__,
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.chat_manager.save_query(session_id, question, response_text, source_info)

            # Generate query ID for source tracking
            query_id = str(uuid.uuid4())

            return {
                "file_id": file_id,
                "operation": operation,
                "result": result,
                "source_info": {
                    "query_id": query_id,
                    "operation": operation,
                    "file_id": file_id,
                    "columns_used": kwargs.get('column'),
                    "result_type": type(result).__name__,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            raise BadRequestException(f"Error executing query: {str(e)}")

    def generate_ai_response(self, question: str, available_files: List[Dict],
                           session_id: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Use OpenAI to understand natural language queries and generate pandas operations"""

        try:
            # Build context with available files and columns
            files_context = "\n".join([
                f"- {f['filename']}: columns {', '.join(f['columns'])}\n  Rows: {f['row_count']}"
                for f in available_files
            ])

            # Build chat history context
            history_context = ""
            if chat_history:
                recent = chat_history[-5:]  # Last 5 interactions
                history_context = "\nRecent Conversation:\n" + "\n".join([
                    f"Q: {entry['question']}\nA: {entry['response'][:200]}{'...' if len(entry['response']) > 200 else ''}"
                    for entry in recent
                ])

            # Use OpenAI to determine the appropriate tool/pandas operation
            client = openai.OpenAI(api_key=settings.openai_api_key)

            context = f"""{history_context}
Available Data Files:
{files_context}

Question: {question}

If this question can be answered with pandas operations, respond with ONLY valid JSON:
{{"tool": "query_data", "parameters": {{"file_id": "user_folder_filename", "operation": "operation_name", "kwargs": {{...}}}}}}

Otherwise respond with:
{{"tool": "none", "reason": "brief explanation why not answerable"}}

Operations: head (show rows), average (column avg), sum (column sum), execute (pandas code), count (row count), describe (stats)
"""

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You analyze data questions and generate pandas operations. Respond ONLY with valid JSON."},
                    {"role": "user", "content": context}
                ],
                temperature=0.1,
                max_tokens=200
            )

            ai_response = response.choices[0].message.content.strip()

            # Clean up response
            if ai_response.startswith("```"):
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
                ai_response = ai_response.strip()

            result = json.loads(ai_response)

            if result.get("tool") == "query_data":
                params = result["parameters"]
                return self.query_data(
                    file_id=params["file_id"],
                    operation=params["operation"],
                    session_id=session_id,
                    question=question,
                    **params.get("kwargs", {})
                )
            else:
                # Can't answer with available data
                polite_response = self._generate_polite_response(question, available_files)

                # Save to chat history
                self.chat_manager.save_query(session_id, question, polite_response, {
                    "classification": "not_relevant",
                    "reason": result.get("reason", "Question not answerable with available data")
                })

                return {
                    "tool": "none",
                    "response": polite_response,
                    "reason": result.get("reason", "Question not answerable with available data")
                }

        except Exception as e:
            raise BadRequestException(f"Error processing AI query: {str(e)}")

    def _generate_polite_response(self, question: str, available_files: List[Dict]) -> str:
        """Generate polite response when question can't be answered"""

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)

            files_info = "\n".join([
                f"- {f['filename']} ({f['row_count']:,} rows, {', '.join(f['columns'][:3])}{'...' if len(f['columns']) > 3 else ''})"
                for f in available_files
            ])

            context = f"""User asked: "{question}"

Available uploaded files:
{files_info}

Please provide a polite, helpful response explaining that the requested information is not available in the uploaded datasets, and suggest what types of questions can be asked about the available data."""

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Be polite and helpful. Explain limitations clearly and suggest alternatives."},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                max_tokens=150
            )

            return response.choices[0].message.content

        except Exception as e:
            return "I'm sorry, but I can only answer questions about data in your uploaded CSV/Excel files. Please try asking about the data columns in your uploaded files!"

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