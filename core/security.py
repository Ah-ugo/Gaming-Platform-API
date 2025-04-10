from datetime import datetime, timedelta
from typing import Any, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from core.config import settings
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    # Ensure subject is already a string
    if not isinstance(subject, str):
        subject = str(subject)
    try:
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode = {
            "exp": expire,
            "sub": str(subject),  # Ensure subject is string
            "role": role,
            "iat": datetime.utcnow(),  # Issued at time
        }

        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm="HS256"
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}")
        raise ValueError("Failed to create access token")


def verify_token(token: str) -> dict:
    """Standalone token verification function"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected token verification error: {str(e)}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing failed: {str(e)}")
        raise ValueError("Failed to hash password")