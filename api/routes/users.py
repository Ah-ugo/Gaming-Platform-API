from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from api.deps import get_admin_user, get_current_active_user
from db.models import User, UserCreate, UserUpdate
from services.user_service import (
    create_user,
    get_user_by_id,
    get_users,
    update_user,
    delete_user
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user)
):
    users = await get_users(skip, limit)
    return users

@router.post("/", response_model=User)
async def create_new_user(
    user_data: UserCreate,
    current_user: User = Depends(get_admin_user)
):
    try:
        user = await create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Internal server error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during user creation",
        )

@router.get("/{user_id}", response_model=User)
async def read_user(
    user_id: str,
    current_user: User = Depends(get_admin_user)
):
    user = await get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=User)
async def update_user_data(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_admin_user)
):
    user = await update_user(user_id, user_data)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/{user_id}", response_model=User)
async def delete_user_data(
    user_id: str,
    current_user: User = Depends(get_admin_user)
):
    user = await delete_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
