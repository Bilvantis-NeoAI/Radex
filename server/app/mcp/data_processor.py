"""
Data Processor for MCP Module

Handles CSV/Excel file processing, caching, and metadata tracking within RADEX.
Uses MinIO for storage instead of local filesystem.
"""

import os
import time
import pandas as pd
from typing import Dict, List, Any, Optional
from functools import lru_cache
from datetime import datetime

from minio import Minio
from minio.error import S3Error
from ..core.exceptions import BadRequestException


class MCPDataProcessor:
    """Handles data processing for MCP analysis within RADEX"""

    def __init__(self, settings):
        self.settings = settings
        self.minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        # Ensure bucket exists
        try:
            if not self.minio_client.bucket_exists(settings.minio_bucket):
                self.minio_client.make_bucket(settings.minio_bucket)
        except S3Error as e:
            print(f"Warning: Could not create MinIO bucket: {e}")
        self.df_cache = {}  # Cache for DataFrames
        self.CACHE_TIMEOUT = 300  # 5 minutes
        self.file_metadata = {}  # file_id -> metadata

    async def upload_file(self, file_data: bytes, filename: str, folder_id: str, user_id: str) -> Dict[str, Any]:
        """Upload a file to MinIO and validate it"""
        try:
            # Validate file type
            if not filename.lower().endswith(('.csv', '.xlsx', '.xls')):
                raise BadRequestException(f"Unsupported file type: {filename}. Only CSV and Excel files are allowed.")

            # Upload to MinIO with MCP subdirectory
            object_name = f"mcp/{user_id}/{folder_id}/{filename}"
            # Convert bytes to file for upload (following RADEX pattern)
            import tempfile
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(file_data)
                temp_file.flush()

                try:
                    self.minio_client.fput_object(
                        self.settings.minio_bucket,
                        object_name,
                        temp_file.name,
                        content_type="application/octet-stream"
                    )
                except S3Error as e:
                    raise BadRequestException(f"Failed to upload file to storage: {str(e)}")

            # Validate by reading the file
            df = self._read_file_from_minio(object_name)

            # Store metadata
            metadata = {
                'upload_time': time.time(),
                'file_size': len(file_data),
                'file_type': 'csv' if filename.lower().endswith('.csv') else 'excel',
                'columns': list(df.columns),
                'row_count': len(df),
                'folder_id': folder_id,
                'user_id': user_id,
                'object_name': object_name,
                'filename': filename
            }

            file_id = f"{user_id}_{folder_id}_{filename}"
            self.file_metadata[file_id] = metadata

            return {
                'file_id': file_id,
                'filename': filename,
                'size': len(file_data),
                'columns': list(df.columns),
                'row_count': len(df),
                'upload_time': metadata['upload_time']
            }

        except Exception as e:
            # Clean up failed upload
            try:
                await self.minio_service.delete_file(self.minio_service.bucket_name, object_name)
            except:
                pass  # Ignore cleanup errors
            raise BadRequestException(f"File upload failed: {str(e)}")

    async def read_file(self, file_id: str) -> pd.DataFrame:
        """Read and cache DataFrame from MinIO"""
        current_time = time.time()

        # Check cache
        if file_id in self.df_cache:
            cached_df, timestamp = self.df_cache[file_id]
            if current_time - timestamp < self.CACHE_TIMEOUT:
                # Update access time
                if file_id in self.file_metadata:
                    self.file_metadata[file_id]['last_accessed'] = current_time
                return cached_df
            else:
                # Cache expired
                del self.df_cache[file_id]

        # Read from MinIO
        if file_id not in self.file_metadata:
            raise BadRequestException(f"File metadata not found: {file_id}")

        metadata = self.file_metadata[file_id]
        object_name = metadata['object_name']

        df = await self._read_file_from_minio(object_name)

        # Cache the DataFrame
        self.df_cache[file_id] = (df.copy(), current_time)

        # Update metadata
        metadata['last_accessed'] = current_time

        return df

    async def _read_file_from_minio(self, object_name: str) -> pd.DataFrame:
        """Read file from MinIO and return DataFrame"""
        try:
            file_data = await self.minio_service.get_file(
                bucket_name=self.minio_service.bucket_name,
                object_name=object_name
            )

            # Create temporary file for pandas to read
            temp_path = f"/tmp/{object_name.split('/')[-1]}"
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

            with open(temp_path, 'wb') as f:
                f.write(file_data)

            try:
                # Read with pandas
                if object_name.lower().endswith('.csv'):
                    df = pd.read_csv(temp_path)
                elif object_name.lower().endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(temp_path)
                else:
                    raise BadRequestException("Unsupported file format")

                return df

            finally:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass

        except Exception as e:
            raise BadRequestException(f"Error reading file from storage: {str(e)}")

    async def list_user_files(self, user_id: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files uploaded by a user, optionally filtered by folder"""
        files_info = []
        for file_id, metadata in self.file_metadata.items():
            if metadata['user_id'] == user_id:
                if folder_id is None or metadata.get('folder_id') == folder_id:
                    files_info.append({
                        "file_id": file_id,
                        "filename": metadata['filename'],
                        "columns": metadata['columns'],
                        "row_count": metadata['row_count'],
                        "file_size": metadata['file_size'],
                        "upload_time": metadata['upload_time'],
                        "last_accessed": metadata.get('last_accessed', metadata['upload_time'])
                    })

        return files_info

    async def describe_file(self, file_id: str) -> Dict[str, Any]:
        """Get detailed information about a file"""
        df = await self.read_file(file_id)

        columns_info = []
        for col in df.columns:
            columns_info.append({
                "name": col,
                "dtype": str(df[col].dtype),
                "non_null_count": int(df[col].count()),
                "null_count": int(df[col].isnull().sum())
            })

        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": columns_info,
            "memory_usage": df.memory_usage(deep=True).sum(),
            "dtypes_summary": df.dtypes.value_counts().to_dict()
        }

    async def get_columns(self, file_id: str) -> List[str]:
        """Get column names for a file"""
        df = await self.read_file(file_id)
        return list(df.columns)

    async def execute_query(self, file_id: str, operation: str, **kwargs) -> Any:
        """Execute a query operation on the data"""
        df = await self.read_file(file_id)

        # Apply filter if provided
        filter_expr = kwargs.get('filter')
        if filter_expr:
            try:
                df = df.query(filter_expr)
            except Exception as e:
                raise BadRequestException(f"Invalid filter expression: {str(e)}")

        # Execute operation
        if operation == "head":
            n = kwargs.get('n', 5)
            return df.head(n).to_dict('records')

        elif operation == "average" and 'column' in kwargs:
            column = kwargs['column']
            if column not in df.columns:
                raise BadRequestException(f"Column '{column}' not found")
            return float(df[column].mean())

        elif operation == "sum" and 'column' in kwargs:
            column = kwargs['column']
            if column not in df.columns:
                raise BadRequestException(f"Column '{column}' not found")
            return float(df[column].sum())

        elif operation == "execute":
            code = kwargs.get('code')
            if not code:
                raise BadRequestException("Code parameter required for execute operation")
            try:
                # Execute pandas code in a controlled environment
                result = eval(code, {"pd": pd, "df": df})
                if hasattr(result, 'to_dict'):
                    if isinstance(result, pd.DataFrame):
                        return result.to_dict('records')
                    else:
                        return result.to_dict()
                else:
                    return result
            except Exception as e:
                raise BadRequestException(f"Error executing code: {str(e)}")

        elif operation == "count":
            return len(df)

        elif operation == "describe":
            return df.describe().to_dict()

        else:
            raise BadRequestException(f"Unsupported operation: {operation}")

    async def delete_file(self, file_id: str) -> bool:
        """Delete a file and its metadata"""
        if file_id not in self.file_metadata:
            return False

        metadata = self.file_metadata[file_id]

        try:
            # Delete from MinIO
            await self.minio_service.delete_file(
                self.minio_service.bucket_name,
                metadata['object_name']
            )

            # Clean up cache and metadata
            if file_id in self.df_cache:
                del self.df_cache[file_id]
            del self.file_metadata[file_id]

            return True
        except Exception as e:
            print(f"Error deleting file {file_id}: {e}")
