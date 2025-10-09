from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from app.models import Permission, Folder, User
from app.core.exceptions import PermissionDeniedException, NotFoundException
from app.logger.logger import setup_logger
from uuid import UUID
logger = setup_logger()

class PermissionService:
    def __init__(self, db: Session):
        self.db = db
    
    def check_folder_permission(
        self,
        user_id: str,
        folder_id: UUID,
        permission_type: str = "read"
    ) -> bool:
        """Check if user has specific permission on folder"""
        logger.info(f"Checking {permission_type} permission for user {user_id} on folder {folder_id}")
        # Check if user is superuser first
        user = self.db.query(User).filter(User.user_id == user_id).first()
        if user and user.is_superuser:
            logger.info(f"User {user_id} is superuser, has all permissions")
            return True
        
        folder = self.db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            logger.warning(f"Folder {folder_id} not found")
            raise NotFoundException("Folder not found")
        
        # Owner has all permissions
        if folder.owner_id == user_id:
            logger.info(f"User {user_id} is owner of folder {folder_id}, has all permissions")
            return True
        
        # Check direct permissions
        permission = self.db.query(Permission).filter(
            Permission.user_id == user_id,
            Permission.folder_id == folder_id
        ).first()
        
        if permission:
            if permission.is_admin:
                logger.info(f"User {user_id} has admin permission on folder {folder_id}")
                return True
            if permission_type == "read" and permission.can_read:
                logger.info(f"User {user_id} has read permission on folder {folder_id}")
                return True
            if permission_type == "write" and permission.can_write:
                logger.info(f"User {user_id} has write permission on folder {folder_id}")
                return True
            if permission_type == "delete" and permission.can_delete:
                logger.info(f"User {user_id} has delete permission on folder {folder_id}")
                return True
        
        # Check parent folder permissions (inheritance)
        if folder.parent_id:
            logger.info(f"Checking what permissions user {user_id} has on parent folder {folder.parent_id}")
            return self.check_folder_permission(user_id, folder.parent_id, permission_type)
        
        logger.info(f"User {user_id} does not have {permission_type} permission on folder {folder_id}")
        return False
    
    def get_user_accessible_folders(self, user_id: str) -> List[Folder]:
        """Get all folders accessible to user"""
        logger.info(f"Fetching all folders accessible to user {user_id}")
        # Check if user is superuser first
        user = self.db.query(User).filter(User.user_id == user_id).first()
        if user and user.is_superuser:
            logger.info(f"User {user_id} is superuser, can access all folders")
            # Superuser can access all folders
            return self.db.query(Folder).all()
        
        # Get folders owned by user
        owned_folders = self.db.query(Folder).filter(Folder.owner_id == user_id).all()
        logger.info(f"User {user_id} owns {len(owned_folders)} folders")

        # Get folders with explicit permissions
        permissions = self.db.query(Permission).filter(
            Permission.user_id == user_id,
            or_(
                Permission.can_read == True,
                Permission.can_write == True,
                Permission.can_delete == True,
                Permission.is_admin == True
            )
        ).all()
        
        permitted_folder_ids = [p.folder_id for p in permissions]
        permitted_folders = self.db.query(Folder).filter(
            Folder.id.in_(permitted_folder_ids)
        ).all() if permitted_folder_ids else []
        
        # Combine and deduplicate
        all_folders = owned_folders + permitted_folders
        unique_folders = {f.id: f for f in all_folders}

        logger.info(f"User {user_id} has access to {len(unique_folders)} folders")
        return list(unique_folders.values())
    
    def grant_permission(
        self,
        granter_id: UUID,
        user_id: str,
        folder_id: UUID,
        can_read: bool = False,
        can_write: bool = False,
        can_delete: bool = False,
        is_admin: bool = False
    ) -> Permission:
        """Grant permission to user for folder"""
        logger.info(f"Granting permissions to user {user_id} for folder {folder_id}")
        # Check if granter is superuser
        granter = self.db.query(User).filter(User.user_id == granter_id).first()
        if not (granter and granter.is_superuser):
            logger.info(f"User {granter_id} is not a superuser. Checking if user has admin rights")
            # If not superuser, check if granter has admin rights
            if not self.check_folder_permission(granter_id, folder_id, "admin"):
                folder = self.db.query(Folder).filter(Folder.id == folder_id).first()
                if not folder or folder.owner_id != granter_id:
                    logger.info(f"User does not have access to folder {folder_id}")
                    raise PermissionDeniedException("You don't have permission to grant access to this folder")
        
        # Check if permission already exists
        existing_permission = self.db.query(Permission).filter(
            Permission.user_id == user_id,
            Permission.folder_id == folder_id
        ).first()
        
        if existing_permission:
            # Update existing permission
            existing_permission.can_read = can_read
            existing_permission.can_write = can_write
            existing_permission.can_delete = can_delete
            existing_permission.is_admin = is_admin
            existing_permission.granted_by = granter_id
            logger.info(f"Existing permission updated for user {user_id} on folder {folder_id} are: read={can_read}, write={can_write}, delete={can_delete}, admin={is_admin}")
            
        else:
            # Create new permission
            existing_permission = Permission(
                user_id=user_id,
                folder_id=folder_id,
                can_read=can_read,
                can_write=can_write,
                can_delete=can_delete,
                is_admin=is_admin,
                granted_by=granter_id
            )
            self.db.add(existing_permission)
            logger.info(f"New permission created for user {user_id} on folder {folder_id} are: read={can_read}, write={can_write}, delete={can_delete}, admin={is_admin}")
        
        self.db.commit()
        self.db.refresh(existing_permission)
        logger.info(f"Permission granted to user {user_id} for folder {folder_id} are: read={can_read}, write={can_write}, delete={can_delete}, admin={is_admin}")
        return existing_permission
    
    def revoke_permission(
        self,
        revoker_id: UUID,
        user_id: str,
        folder_id: UUID
    ) -> bool:
        """Revoke user's permission for folder"""
        logger.info(f"Revoking permissions of user {user_id} for folder {folder_id}")
        # Check if revoker is superuser
        revoker = self.db.query(User).filter(User.user_id == revoker_id).first()
        if not (revoker and revoker.is_superuser):
            logger.info(f"User {revoker_id} is not a superuser. Checking if user has admin rights")
            # If not superuser, check if revoker has admin rights
            folder = self.db.query(Folder).filter(Folder.id == folder_id).first()
            if not folder:
                logger.warning(f"Folder {folder_id} not found")
                raise NotFoundException("Folder not found")
            
            if folder.owner_id != revoker_id and not self.check_folder_permission(revoker_id, folder_id, "admin"):
                logger.info(f"User does not have permission to revoke access to folder {folder_id}")
                raise PermissionDeniedException("You don't have permission to revoke access to this folder")
        
        permission = self.db.query(Permission).filter(
            Permission.user_id == user_id,
            Permission.folder_id == folder_id
        ).first()
        logger.info(f"Found permission: {permission}")
        if permission:
            self.db.delete(permission)
            self.db.commit()
            logger.info(f"Permission revoked for user {user_id} on folder {folder_id}")
            return True
        logger.info(f"No permission found for user {user_id} on folder {folder_id} to revoke")
        return False
    
    def get_folder_permissions(self, folder_id: UUID) -> List[Permission]:
        """Get all permissions for a folder"""
        logger.info(f"Fetching all permissions for folder {folder_id}")
        permission = (self.db.query(Permission)
        .options(joinedload(Permission.user))
        .filter(
            Permission.folder_id == folder_id
        ).all()
        )
        logger.info(f"Found these permissions for folder {folder_id}: {permission}")
        return permission
    
    def check_folder_access(self, user_id: str, folder_id: UUID, permission_type: str = "read"):
        """Check folder access and raise exception if denied"""
        logger.info(f"Checking access for user {user_id} on folder {folder_id} for permission type {permission_type}")
        if not self.check_folder_permission(user_id, folder_id, permission_type):
            logger.warning(f"User {user_id} does not have {permission_type} permission on folder {folder_id}")
            raise PermissionDeniedException(f"You don't have {permission_type} permission for this folder")
        else:
            logger.info(f"User has {permission_type} permission on folder {folder_id}")