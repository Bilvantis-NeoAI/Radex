from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import UserCreate, User, Token, UserLogin, UserBase
from app.services.auth_service import AuthService
from app.core.security import create_access_token
from app.core.dependencies import get_current_active_user
from app.config import settings
from app.firebase import initialize_firebase
from app.logger.logger import setup_logger
from datetime import datetime
logger = setup_logger()

router = APIRouter()

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    try:
        auth_service = AuthService(db)
        user = auth_service.create_user(user_data)
        logger.info(f"User Registered Successfully: {user_data.username}")
        return user
    except Exception as e:
        logger.error(f"Error during user registration: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/okta_login", response_model=Token)
def okta_login(
    user_data: dict,
    db: Session = Depends(get_db)
):
    logger.info("Processing Okta login request")
    initialize_firebase()
    """Receive Firebase login result, verify if user exists in db, verify ID token, and sync user info."""
    try:
        id_token = user_data.get("user", {}).get("stsTokenManager", {}).get("accessToken")
        if not id_token:
            raise HTTPException(status_code=400, detail="Missing ID token")

        logger.info(f"Received user payload: {user_data}")

        okta_user = user_data['user']
        provider_id = user_data['providerId']
        _tokenResponse = user_data["_tokenResponse"]
        operationType = user_data["operationType"]
        provider_data = okta_user.get("providerData", [])

        okta_user_id = provider_data[0].get("uid")
        access_token = okta_user["stsTokenManager"]["accessToken"]
        auth_service = AuthService(db)
        user = auth_service.authenticate_okta_user(okta_user_id)
        groups = auth_service.get_groups_by_user(okta_user_id)
        logger.info(f"the groups for this user are: {groups}")
        roles = auth_service.get_user_role(okta_user_id)
        logger.info(f"ROLE: {roles}")
        role = []
        if len(roles) == 1:
            role.append(roles[0]['label'])
        else:
            for r in roles:
                role.append(r['label'])
        logger.info(f"Roles for user {okta_user_id}: {role}")
        username = _tokenResponse['firstName'] + "_" + _tokenResponse['lastName']
        if not user:
            # Map Firebase user fields into OktaUser schema
            user_data = User(
                user_id=okta_user_id,                          # ID token we extracted
                email=okta_user["email"],
                username=username,
                groups=groups,
                roles =role,
                auth_provider="okta",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            user = auth_service.create_okta_user(user_data)
        logger.info("Okta login completed successfully")
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error during Okta login: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    logger.info("Processing standard login request")
    """Login and receive access token"""
    try:
        auth_service = AuthService(db)
        user = auth_service.authenticate_user(form_data.username, form_data.password)
        
        if not user:
            logger.warning(f"Incorrect username or password for standardlogin attempt for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            logger.warning(f"Inactive user login for standard login attempt: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        access_token_expires = timedelta(minutes=settings.jwt_expiration_minutes)
        access_token = create_access_token(
            data={"sub": str(user.user_id)}, expires_delta=access_token_expires
        )

        logger.info(f"Standard User Logged In Successfully")
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        logger.error(f"Error during standard login: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    try:
        logger.info(f"Current user info retrieved: {current_user.username}, {current_user.email}")
        return current_user
    except Exception as e:
        logger.error(f"Error getting current user info: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"Refreshing token for user: {current_user.username}")
    """Refresh access token"""
    try:
        access_token_expires = timedelta(minutes=settings.jwt_expiration_minutes)
        access_token = create_access_token(
            data={"sub": str(current_user.user_id)}, expires_delta=access_token_expires
        )
        
        logger.info(f"Token refreshed successfully for user")
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error getting refresh token: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Deleting user account: {current_user.user_id}")
    """Delete current user account and all associated data"""
    try:
        auth_service = AuthService(db)
        auth_service.delete_user(str(current_user.user_id))
        return None
    except Exception as e:
        logger.error(f"Error deleting user account: {e}")
        raise HTTPException(status_code=400, detail=str(e))