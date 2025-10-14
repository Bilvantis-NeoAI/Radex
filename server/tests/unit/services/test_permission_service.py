"""
Unit tests for permission service.
Tests access control and permission checking logic.
"""
import pytest
from unittest.mock import Mock
from uuid import uuid4
from app.services.permission_service import PermissionService
from app.core.exceptions import PermissionDeniedException, NotFoundException


class TestCheckFolderPermission:
    """Test checking folder permissions"""

    def test_superuser_has_all_permissions(self, mock_db, sample_admin_user, sample_folder):
        """Test that superuser has all permissions"""
        service = PermissionService(mock_db)

        # Mock the queries
        mock_db.query().filter().first.side_effect = [sample_admin_user, sample_folder]

        result = service.check_folder_permission(
            sample_admin_user.id,
            sample_folder.id,
            "read"
        )

        assert result is True

    def test_owner_has_all_permissions(self, mock_db, sample_user, sample_folder):
        """Test that folder owner has all permissions"""
        service = PermissionService(mock_db)

        # Set user as owner
        sample_folder.owner_id = sample_user.id
        sample_user.is_superuser = False

        mock_db.query().filter().first.side_effect = [sample_user, sample_folder]

        result = service.check_folder_permission(
            sample_user.id,
            sample_folder.id,
            "write"
        )

        assert result is True

    def test_folder_not_found_raises_exception(self, mock_db, sample_user):
        """Test that missing folder raises NotFoundException"""
        service = PermissionService(mock_db)

        mock_db.query().filter().first.side_effect = [sample_user, None]

        with pytest.raises(NotFoundException, match="Folder not found"):
            service.check_folder_permission(
                sample_user.id,
                uuid4(),
                "read"
            )

    def test_user_with_read_permission(self, mock_db, sample_user, sample_folder, sample_permission):
        """Test user with explicit read permission"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_folder.owner_id = uuid4()  # Different owner
        sample_permission.can_read = True
        sample_permission.can_write = False

        mock_db.query().filter().first.side_effect = [
            sample_user,
            sample_folder,
            sample_permission
        ]

        result = service.check_folder_permission(
            sample_user.id,
            sample_folder.id,
            "read"
        )

        assert result is True

    def test_user_without_write_permission(self, mock_db, sample_user, sample_folder, sample_permission):
        """Test user without write permission"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_folder.owner_id = uuid4()
        sample_folder.parent_id = None
        sample_permission.can_read = True
        sample_permission.can_write = False

        mock_db.query().filter().first.side_effect = [
            sample_user,
            sample_folder,
            sample_permission
        ]

        result = service.check_folder_permission(
            sample_user.id,
            sample_folder.id,
            "write"
        )

        assert result is False

    def test_admin_permission_grants_all_access(self, mock_db, sample_user, sample_folder, sample_permission):
        """Test that is_admin permission grants all access"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_folder.owner_id = uuid4()
        sample_permission.is_admin = True
        sample_permission.can_read = False
        sample_permission.can_write = False

        mock_db.query().filter().first.side_effect = [
            sample_user,
            sample_folder,
            sample_permission
        ]

        result = service.check_folder_permission(
            sample_user.id,
            sample_folder.id,
            "write"
        )

        assert result is True


class TestGetUserAccessibleFolders:
    """Test getting accessible folders for user"""

    def test_superuser_gets_all_folders(self, mock_db, sample_admin_user, sample_folder):
        """Test superuser gets all folders"""
        service = PermissionService(mock_db)

        all_folders = [sample_folder]
        mock_db.query().filter().first.return_value = sample_admin_user
        mock_db.query().all.return_value = all_folders

        result = service.get_user_accessible_folders(sample_admin_user.id)

        assert result == all_folders

    def test_user_gets_owned_folders(self, mock_db, sample_user, sample_folder):
        """Test user gets folders they own"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_folder.owner_id = sample_user.id

        mock_db.query().filter().first.return_value = sample_user
        mock_db.query().filter().all.return_value = [sample_folder]
        mock_db.query().filter().all.return_value = []  # No permissions

        # Mock second query for permissions
        mock_perm_query = Mock()
        mock_perm_query.all.return_value = []
        mock_db.query().filter.return_value = mock_perm_query

        result = service.get_user_accessible_folders(sample_user.id)

        assert len(result) >= 1

    def test_user_gets_permitted_folders(self, mock_db, sample_user, sample_folder, sample_permission):
        """Test user gets folders with explicit permissions"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_permission.can_read = True

        # Setup complex mock chain
        mock_db.query().filter().first.return_value = sample_user

        # Mock owned folders query
        owned_query = Mock()
        owned_query.all.return_value = []
        mock_db.query().filter.return_value = owned_query

        result = service.get_user_accessible_folders(sample_user.id)

        assert isinstance(result, list)

    def test_deduplicates_folders(self, mock_db, sample_user, sample_folder):
        """Test that duplicate folders are removed"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False

        # User owns the folder AND has permission to it
        mock_db.query().filter().first.return_value = sample_user

        result = service.get_user_accessible_folders(sample_user.id)

        # Should not contain duplicates
        folder_ids = [f.id for f in result]
        assert len(folder_ids) == len(set(folder_ids))


class TestGrantPermission:
    """Test granting permissions"""

    def test_superuser_can_grant_permission(self, mock_db, sample_admin_user, sample_user, sample_folder):
        """Test superuser can grant permissions"""
        service = PermissionService(mock_db)

        mock_db.query().filter().first.side_effect = [
            sample_admin_user,  # granter
            sample_folder,
            None  # no existing permission
        ]

        # Mock Permission creation
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = service.grant_permission(
            granter_id=sample_admin_user.id,
            user_id=sample_user.id,
            folder_id=sample_folder.id,
            can_read=True
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_owner_can_grant_permission(self, mock_db, sample_user, sample_folder):
        """Test folder owner can grant permissions"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_folder.owner_id = sample_user.id

        mock_db.query().filter().first.side_effect = [
            sample_user,  # granter (not superuser)
            sample_folder,  # folder owned by granter
            None  # no existing permission
        ]

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = service.grant_permission(
            granter_id=sample_user.id,
            user_id=uuid4(),
            folder_id=sample_folder.id,
            can_read=True
        )

        mock_db.add.assert_called_once()

    def test_non_admin_non_owner_cannot_grant(self, mock_db, sample_user, sample_folder):
        """Test non-admin, non-owner cannot grant permissions"""
        service = PermissionService(mock_db)

        sample_user.is_superuser = False
        sample_folder.owner_id = uuid4()  # Different owner

        mock_db.query().filter().first.side_effect = [
            sample_user,
            sample_folder
        ]

        with pytest.raises(PermissionDeniedException):
            service.grant_permission(
                granter_id=sample_user.id,
                user_id=uuid4(),
                folder_id=sample_folder.id,
                can_read=True
            )

    def test_updates_existing_permission(self, mock_db, sample_admin_user, sample_user, sample_folder, sample_permission):
        """Test updating existing permission"""
        service = PermissionService(mock_db)

        existing_permission = sample_permission
        existing_permission.can_read = False
        existing_permission.can_write = False

        mock_db.query().filter().first.side_effect = [
            sample_admin_user,
            sample_folder,
            existing_permission
        ]

        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = service.grant_permission(
            granter_id=sample_admin_user.id,
            user_id=sample_user.id,
            folder_id=sample_folder.id,
            can_read=True,
            can_write=True
        )

        # Should update existing permission
        assert existing_permission.can_read is True
        assert existing_permission.can_write is True
        mock_db.commit.assert_called_once()
