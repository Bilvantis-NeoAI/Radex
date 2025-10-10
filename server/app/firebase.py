import json
import firebase_admin
from firebase_admin import credentials
from app.config import settings
from app.logger.logger import setup_logger

logger = setup_logger()

def initialize_firebase():
    """Initializes Firebase Admin SDK once with proper error handling."""
    if firebase_admin._apps:
        logger.info("Firebase Admin SDK already initialized.")
        return firebase_admin.get_app()

    if not settings.firebase_admin_sdk_json:
        logger.error("Firebase Admin SDK JSON not found in environment variables. Firebase not initialized.")
        raise ValueError("Missing Firebase Admin SDK credentials.")

    try:
        cred_json = json.loads(settings.firebase_admin_sdk_json)
        cred = credentials.Certificate(cred_json)
        app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully.")
        return app

    except json.JSONDecodeError as e:
        logger.exception(f"Failed to parse Firebase credentials JSON: {e}")
        raise

    except ValueError as e:
        logger.exception(f"Invalid Firebase credentials: {e}")
        raise

    except Exception as e:
        logger.exception(f"Unexpected error initializing Firebase Admin SDK: {e}")
        raise
