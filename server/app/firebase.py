import json
import firebase_admin
from firebase_admin import credentials
from app.config import settings
from app.logger.logger import setup_logger

logger = setup_logger()


def initialize_firebase():
    # Initialize Firebase Admin SDK (once)
    if not firebase_admin._apps:
        if settings.firebase_admin_sdk_json:
            cred_json = json.loads(settings.firebase_admin_sdk_json)
            cred = credentials.Certificate(cred_json)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized.")
        else:
            # Fallback or error if credentials are not provided
            logger.error("Firebase Admin SDK JSON not found in environment variables. Firebase not initialized.")