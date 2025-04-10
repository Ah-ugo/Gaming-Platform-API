from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from core.config import settings
from db.database import get_database
from db.models import TokenData, UserRole
from services.user_service import get_user_by_id
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")

        if not user_id:
            raise credentials_exception

        # Get user with proper ID conversion
        user = await get_user_by_id(user_id)
        if not user:
            raise credentials_exception

        return user
    except (JWTError, ValidationError) as e:
        raise credentials_exception

async def get_current_active_user(current_user=Depends(get_current_user)):
    if not current_user.is_active:
        logger.warning(f"Inactive user access attempt: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_admin_user(current_user=Depends(get_current_active_user)):
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized admin access attempt by: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user