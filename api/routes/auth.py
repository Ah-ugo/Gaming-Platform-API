from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from core.config import settings
from core.security import create_access_token
from db.models import Token, User, UserCreate
from db.database import get_database
from services.user_service import authenticate_user, create_user
from api.deps import get_current_active_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Add debug logging
    logger.debug(f"Login attempt for: {form_data.username}")

    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        # More detailed error message
        db = get_database()
        exists = await db.users.find_one({"email": form_data.username})

        if exists:
            raise HTTPException(
                status_code=400,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Verify the user ID is properly set
    if not hasattr(user, "id") or not user.id:
        logger.error(f"User object missing ID: {user}")
        raise HTTPException(
            status_code=500,
            detail="Invalid user data",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=User)
async def register_user(user_data: UserCreate):
    try:
        user = await create_user(user_data)
        return user
    except ValueError as e:
        # Check if user was actually created
        db = get_database()
        existing_user = await db.users.find_one({"email": user_data.email})
        if existing_user:
            logger.error(f"User created but model validation failed for: {existing_user}")
            # Try to return basic user data if full validation failed
            return {
                "id": str(existing_user["_id"]),
                "email": existing_user["email"],
                "first_name": existing_user["first_name"],
                "last_name": existing_user["last_name"],
                "is_active": existing_user.get("is_active", True),
                "role": existing_user.get("role", "user")
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Server error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
