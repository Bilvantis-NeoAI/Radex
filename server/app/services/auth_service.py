from typing import Optional
from sqlalchemy.orm import Session
from app.models import User, OktaUser
from app.schemas import UserCreate, UserUpdate, OktaUserSchema, OktaUserUpdate
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import BadRequestException, NotFoundException, ConflictException, HTTPException
from app.config import settings
import requests

class AuthService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, user_data: UserCreate) -> User:
        # Check if user with email already exists
        if self.db.query(User).filter(User.email == user_data.email).first():
            raise ConflictException("User with this email already exists")
        
        # Check if user with username already exists
        if self.db.query(User).filter(User.username == user_data.username).first():
            raise ConflictException("User with this username already exists")
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=user_data.is_active,
            is_superuser=False  # Always False for API registrations - security measure
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
        
    def create_okta_user(self, user_data: OktaUserSchema) -> OktaUser:
        # Check if user with email already exists
        db_user = self.db.query(OktaUser).filter(OktaUser.email == user_data.email).first()
        if db_user:
            return db_user

        # Create new user
        db_user = OktaUser(
            okta_user_id=user_data.okta_user_id,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            groups=user_data.groups,
            roles=user_data.roles,
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def get_groups_by_user(self, okta_user_id:str) -> Optional[OktaUser]:
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
                print(group["id"], group_name)
                user_groups.append(group_name)
            return user_groups
        else:
            print("Failed to fetch user groups:", response.status_code, response.text)
            raise HTTPException(status_code=response.status_code, detail=response.text)

    def get_user_role(self, okta_user_id:str) -> Optional[OktaUser]:
        headers = {
        "Authorization": f"SSWS {settings.OKTA_API_TOKEN}",
        "Accept": "application/json"
        }
        print(f"okta user id: {okta_user_id}")

        url = f"{settings.OKTA_DOMAIN}/api/v1/users/{okta_user_id}/roles"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        roles = response.json()
        return roles

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()
    
    def authenticate_okta_user(self, okta_user_id: str) -> Optional[OktaUser]:
        user = self.db.query(OktaUser).filter(OktaUser.okta_user_id == okta_user_id).first()
        if not user:
            return None
        # Note: Password verification is not applicable for Okta users in this context
        return user

    def get_okta_user_by_oktaid(self, okta_user_id: str) -> Optional[OktaUser]:
        return self.db.query(OktaUser).filter(OktaUser.okta_user_id == okta_user_id).first()

    def get_okta_users_by_firstname(self, first_name: str) -> list[OktaUser]:
        return self.db.query(OktaUser).filter(OktaUser.first_name == first_name).all()

    def get_okta_users_by_lastname(self, last_name: str) -> list[OktaUser]:
        return self.db.query(OktaUser).filter(OktaUser.last_name == last_name).all()

    def search_okta_users_by_email(self, email_substring: str) -> list[OktaUser]:
        return self.db.query(OktaUser).filter(OktaUser.email.ilike(f"%{email_substring}%")).all()

    def update_user(self, user_id: str, user_update: UserUpdate) -> User:
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        update_data = user_update.dict(exclude_unset=True)
        
        # Check for conflicts if email or username is being updated
        if "email" in update_data:
            existing_user = self.db.query(User).filter(
                User.email == update_data["email"],
                User.id != user_id
            ).first()
            if existing_user:
                raise ConflictException("User with this email already exists")
        
        if "username" in update_data:
            existing_user = self.db.query(User).filter(
                User.username == update_data["username"],
                User.id != user_id
            ).first()
            if existing_user:
                raise ConflictException("User with this username already exists")
        
        # Hash password if it's being updated
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_okta_user(self, update_data: OktaUserUpdate) -> OktaUser:
        user = self.get_okta_user_by_oktaid(update_data.okta_user_id)
        if not user:
            raise NotFoundException("Okta user not found")

        update_fields = update_data.dict(exclude_unset=True)
        update_fields.pop("okta_user_id")  # don't overwrite the ID

        for field, value in update_fields.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        self.db.delete(user)
        self.db.commit()
        return True
    
    def create_user_admin(self, user_data) -> User:
        """Create user with admin privileges (can set superuser status)"""
        # Check if user with email already exists
        if self.db.query(User).filter(User.email == user_data.email).first():
            raise ConflictException("User with this email already exists")
        
        # Check if user with username already exists
        if self.db.query(User).filter(User.username == user_data.username).first():
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
        return db_user
    
    def update_user_admin(self, user_id: str, user_update) -> User:
        """Update user with admin privileges (can set superuser status)"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        update_data = user_update.dict(exclude_unset=True)
        
        # Check for conflicts if email or username is being updated
        if "email" in update_data:
            existing_user = self.db.query(User).filter(
                User.email == update_data["email"],
                User.id != user_id
            ).first()
            if existing_user:
                raise ConflictException("User with this email already exists")
        
        if "username" in update_data:
            existing_user = self.db.query(User).filter(
                User.username == update_data["username"],
                User.id != user_id
            ).first()
            if existing_user:
                raise ConflictException("User with this username already exists")
        
        # Hash password if it's being updated
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data["password"])
            del update_data["password"]
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user