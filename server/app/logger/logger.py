import logging
import uuid
import os
from typing import Optional
from contextvars import ContextVar
from functools import wraps
from logging.handlers import TimedRotatingFileHandler

# Context variable to store the request ID
request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

# Ensure the 'logs' directory exists
os.makedirs('logs', exist_ok=True)

class RequestIdFilter(logging.Filter):
    """Filter that adds request_id to log records"""
    def filter(self, record):
        record.request_id = request_id_context.get() or '-'
        return True

def setup_logger(
    level: int = logging.INFO,
    log_format: Optional[str] = None,
    log_file: str = 'logs/app.log',  # Base log file name
    backup_count: int = 7  # Number of days to retain old logs
    ) -> logging.Logger:
    """Configure and return a logger instance for the application."""
    if log_format is None:
        # Include request_id in the format
        log_format = '%(asctime)s - [%(request_id)s] - %(name)s - %(levelname)s - %(message)s'

    # Configure basic logging
    logger = logging.getLogger('app')
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Create a timed rotating file handler for daily rotation
    rotating_file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=backup_count, encoding='utf-8'
    )
    rotating_file_handler.setFormatter(logging.Formatter(log_format))

    # Add the request ID filter
    logger.addFilter(RequestIdFilter())

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(rotating_file_handler)

    return logger

def with_request_id(func):
    """Decorator to add request ID to the context"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())
        token = request_id_context.set(request_id)
        try:
            return await func(*args, **kwargs)
        finally:
            request_id_context.reset(token)
    return wrapper

logger = setup_logger()

def retrieve_logger():
    return logger