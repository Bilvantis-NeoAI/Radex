from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import UserCreate, User, Token, UserLogin, OktaUserSchema, OktaUser
from app.services.auth_service import AuthService
from app.core.security import create_access_token
from app.core.dependencies import get_current_okta_user, get_current_active_user
from app.config import settings
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

router = APIRouter()

# Initialize Firebase Admin SDK (once)
if not firebase_admin._apps:
    cred = credentials.Certificate("app/billgo-llm-firebase-adminsdk-fbsvc-cbf7a7bb2c.json")
    firebase_admin.initialize_app(cred)

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    user = auth_service.create_user(user_data)
    return user

@router.post("/okta_login", response_model=Token)
def okta_login(
    user_data: dict,
    db: Session = Depends(get_db)
):
    print("Inside okta login")
    """Receive Firebase login result, verify if user exists in db, verify ID token, and sync user info."""
    id_token = user_data.get("user", {}).get("stsTokenManager", {}).get("accessToken")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing ID token")

    print(len(user_data))
    for keys in user_data:
        print(keys)
    print(f"Recieved user payload: {user_data}")

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
    print(f"the groups for this user are: {groups}")
    roles = auth_service.get_user_role(okta_user_id)
    print(f"ROLE: {roles}")
    role = roles[0]['label']
    print(role)
    if not user:
        # Map Firebase user fields into OktaUser schema
        user_data = OktaUserSchema(
            okta_user_id=provider_data[0].get("uid"),                          # ID token we extracted
            email=okta_user["email"],
            first_name=_tokenResponse['firstName'],
            last_name=_tokenResponse['lastName'],
            groups=groups,
            roles = role,
        )

        user = auth_service.create_okta_user(user_data)

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and receive access token"""
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=settings.jwt_expiration_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return current_user

# Endpoint to get current user info
@router.get("/okta_me", response_model=OktaUserSchema)
async def get_current_okta_user_info(
    current_user: OktaUser = Depends(get_current_okta_user)
):
    """Get current Okta user information"""
    print(type(current_user))
    return current_user

@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_active_user)
):
    """Refresh access token"""
    access_token_expires = timedelta(minutes=settings.jwt_expiration_minutes)
    access_token = create_access_token(
        data={"sub": str(current_user.id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete current user account and all associated data"""
    auth_service = AuthService(db)
    auth_service.delete_user(str(current_user.id))
    return None