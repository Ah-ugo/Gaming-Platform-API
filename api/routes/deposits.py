from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from api.deps import get_admin_user, get_current_active_user
from db.models import Deposit, DepositCreate, DepositUpdate, User
from services.deposit_service import (
    create_deposit,
    get_deposit_by_id,
    get_deposits,
    get_pending_deposits,
    update_deposit,
    approve_deposit,
    reject_deposit
)
import logging


logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[Deposit])
async def read_deposits(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user)
):
    deposits = await get_deposits(skip, limit)
    return deposits

@router.get("/pending", response_model=List[Deposit])
async def read_pending_deposits(
    current_user: User = Depends(get_admin_user)
):
    deposits = await get_pending_deposits()
    return deposits

@router.post("/", response_model=Deposit)
async def create_new_deposit(
    deposit_data: DepositCreate,
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Override user_id with current user's ID
        deposit_data.user_id = current_user.id
        deposit = await create_deposit(deposit_data)
        return deposit
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Internal server error creating deposit: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during deposit creation",
        )

@router.get("/{deposit_id}", response_model=Deposit)
async def read_deposit(
    deposit_id: str,
    current_user: User = Depends(get_admin_user)
):
    deposit = await get_deposit_by_id(deposit_id)
    if deposit is None:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return deposit

@router.put("/{deposit_id}", response_model=Deposit)
async def update_deposit_data(
    deposit_id: str,
    deposit_data: DepositUpdate,
    current_user: User = Depends(get_admin_user)
):
    deposit = await update_deposit(deposit_id, deposit_data)
    if deposit is None:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return deposit


@router.post("/{deposit_id}/approve", response_model=Deposit)
async def approve_deposit_endpoint(
        deposit_id: str,
        current_user: User = Depends(get_admin_user)
):
    # First check if deposit exists
    existing_deposit = await get_deposit_by_id(deposit_id)
    if not existing_deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )

    # Then attempt approval
    deposit = await approve_deposit(deposit_id)
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit approval failed"
        )

    return deposit

@router.post("/{deposit_id}/reject", response_model=Deposit)
async def reject_deposit_endpoint(
    deposit_id: str,
    current_user: User = Depends(get_admin_user)
):
    deposit = await reject_deposit(deposit_id)
    if deposit is None:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return deposit
