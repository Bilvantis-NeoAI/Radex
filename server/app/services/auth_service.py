import token
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import Depends, status, Request
from app.models import User
from app.schemas import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.database import get_db
from app.core.exceptions import BadRequestException, NotFoundException, ConflictException, HTTPException
from app.config import settings
from app.logger.logger import setup_logger
import requests
import uuid
logger = setup_logger()

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.okta_domain = settings.OKTA_DOMAIN
    
    def create_user(self, user_data: UserCreate) -> User:
        # Check if user with email already exists
        if self.db.query(User).filter(User.email == user_data.email).first():
            logger.warning(f"User with email {user_data.email} already exists")
            raise ConflictException("User with this email already exists")
        
        # Check if user with username already exists
        if self.db.query(User).filter(User.username == user_data.username).first():
            logger.warning(f"User with username {user_data.username} already exists")
            raise ConflictException("User with this username already exists")
        
        user_id = str(uuid.uuid4())

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            user_id=user_id,
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=user_data.is_active,
            is_superuser=False  # Always False for API registrations - security measure
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"New user created with ID: {user_id}")
        return db_user
        
    def create_okta_user(self, user_data: UserCreate) -> User:
        # Check if user with email already exists
        db_user = self.db.query(User).filter(User.email == user_data.email).first()
        if db_user:
            logger.info(f"Okta user with email {user_data.email} already exists")
            return db_user

        # Create new user
        db_user = User(
            user_id=user_data.user_id,
            email=user_data.email,
            username=user_data.username,
            groups=user_data.groups,
            roles=user_data.roles,
            auth_provider="okta",  # <-- critical
            is_superuser=True if "Super Administrator" in user_data.roles else False,
            hashed_password=None
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"New Okta user created with ID: {user_data.user_id}")
        return db_user

    def get_groups_by_user(self, okta_user_id:str) -> Optional[User]:
        logger.info(f"Fetching groups for Okta user ID: {okta_user_id}")
        user_groups = []
        headers = {
            "Authorization": f"SSWS {settings.OKTA_API_TOKEN}",
            "Accept": "application/json"
            }
        
        # Get list of groups assigned to the user
        url = f"{settings.OKTA_DOMAIN}/api/v1/users/{okta_user_id}/groups"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            groups = response.json()
            for group in groups:
                group_name = group["profile"].get("name", "Unnamed Group")
                logger.info(f"Group found: {group['id']} - {group_name}")
                user_groups.append(group_name)
            return user_groups
        else:
            logger.error(f"Failed to fetch user groups: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

    def get_user_role(self, okta_user_id:str) -> Optional[User]:
        headers = {
        "Authorization": f"SSWS {settings.OKTA_API_TOKEN}",
        "Accept": "application/json"
        }
        logger.info(f"Okta user id: {okta_user_id}")

        url = f"{settings.OKTA_DOMAIN}/api/v1/users/{okta_user_id}/roles"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch user roles: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        roles = response.json()
        logger.info(f"Roles fetched for user {okta_user_id}: {roles}")
        return roles

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        logger.info(f"Authenticating user: {username}")
        user = self.db.query(User).filter(User.username == username).first()
        if not user:
            logger.warning(f"User not found: {username}")
            return None
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Invalid password for user: {username}")
            return None
        logger.info(f"User {username} authenticated successfully")
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        logger.info(f"Fetching user by ID: {user_id}")
        user_by_id = self.db.query(User).filter(User.user_id == user_id).first()
        if user_by_id:
            logger.info(f"User found: {user_by_id.username} with ID: {user_id}")
        else:
            logger.warning(f"No user found with ID: {user_id}")
        return user_by_id
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        logger.info(f"Fetching user by email: {email}")
        user_by_email = self.db.query(User).filter(User.email == email).first()
        if user_by_email:
            logger.info(f"User found: {user_by_email.username} with email: {email}")
        else:
            logger.warning(f"No user found with email: {email}")
        return user_by_email
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        logger.info(f"Fetching user by username: {username}")
        user_by_username = self.db.query(User).filter(User.username == username).first()
        if user_by_username:
            logger.info(f"User found: {user_by_username.username}")
        else:
            logger.warning(f"No user found with username: {username}")
        return user_by_username

        # user_id = decoded_token.get("sub")
        # scopes = decoded_token.get("scp", [])
        # audience = decoded_token.get("aud")
        # logger.info(f"Decoded Okta token for user ID: {user_id}, audience: {audience}, scopes: {scopes}")
        # if user_id == okta_user_id:
        #     logger.info(f"Okta token verified for user ID: {user_id}")

    def authenticate_okta_user(self,  okta_user_id: str) -> Optional[User]:
        logger.info(f"Authenticating Okta user ID: {okta_user_id}")
        user = self.db.query(User).filter(User.user_id == okta_user_id).first()
        if not user:
            logger.warning(f"Okta user not found with ID: {okta_user_id}")
            return None
        # Note: Password verification is not applicable for Okta users in this context
        logger.info(f"Okta user {user.username} authenticated successfully")
        return user

    def update_user(self, user_id: str, user_update: UserUpdate) -> User:
        logger.info(f"Updating user: {user_id}")
        user = self.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User not found with ID: {user_id}")
            raise NotFoundException("User not found")
        if user.auth_provider == "okta":
            logger.warning(f"Attempt to update Okta user details for user ID: {user_id}")
            raise ConflictException("Cannot update okta users details")
        
        update_data = user_update.dict(exclude_unset=True)
        
        # Check for conflicts if email or username is being updated
        if "email" in update_data:
            logger.info(f"Checking for email conflict: {update_data['email']}")
            existing_user = self.db.query(User).filter(
                User.email == update_data["email"],
                User.user_id != user_id
            ).first()
            if existing_user:
                logger.warning(f"Conflict: User with email {update_data['email']} already exists")  
                raise ConflictException("User with this email already exists")
            else:
                logger.info(f"No conflict found")        
        if "username" in update_data:
            existing_user = self.db.query(User).filter(
                User.username == update_data["username"],
                User.user_id != user_id
            ).first()
            if existing_user:
                logger.warning(f"Conflict: User with username {update_data['username']} already exists")
                raise ConflictException("User with this username already exists")
            else:
                logger.info(f"No conflict found")
        
        # Hash password if it's being updated
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User {user_id} updated successfully")
        return user
    
    def delete_user(self, user_id: str) -> bool:
        logger.info(f"Deleting user with ID: {user_id}")
        user = self.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User not found with ID: {user_id}")
            raise NotFoundException("User not found")
        
        self.db.delete(user)
        self.db.commit()
        logger.info(f"User {user_id} deleted successfully")
        return True
    
    def create_user_admin(self, user_data) -> User:
        """Create user with admin privileges (can set superuser status)"""
        logger.info(f"Creating admin user with email: {user_data.email}")
        # Check if user with email already exists
        if self.db.query(User).filter(User.email == user_data.email).first():
            logger.warning(f"User with email {user_data.email} already exists")
            raise ConflictException("User with this email already exists")
        
        # Check if user with username already exists
        if self.db.query(User).filter(User.username == user_data.username).first():
            logger.warning(f"User with username {user_data.username} already exists")
            raise ConflictException("User with this username already exists")
        
        # Create new user with admin privileges
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser  # Admin can set superuser status
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"Admin user created with ID: {db_user.user_id}")
        return db_user
    
    def update_user_admin(self, user_id: str, user_update) -> User:
        """Update user with admin privileges (can set superuser status)"""
        logger.info(f"Admin updating user: {user_id} with data: {user_update}")
        user = self.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User not found with ID: {user_id}")
            raise NotFoundException("User not found")
        
        update_data = user_update.dict(exclude_unset=True)
        
        # Check for conflicts if email or username is being updated
        if "email" in update_data:
            logger.info(f"Checking for email conflict")
            existing_user = self.db.query(User).filter(
                User.email == update_data["email"],
                User.user_id != user_id
            ).first()
            if existing_user:
                logger.warning(f"Conflict: User with email {update_data['email']} already exists")
                raise ConflictException("User with this email already exists")
        
        if "username" in update_data:
            logger.info(f"Checking for username conflict")
            existing_user = self.db.query(User).filter(
                User.username == update_data["username"],
                User.user_id != user_id
            ).first()
            if existing_user:
                logger.warning(f"Conflict: User with username {update_data['username']} already exists")
                raise ConflictException("User with this username already exists")
        
        # Hash password if it's being updated
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User {user_id} updated successfully by admin")
        return user