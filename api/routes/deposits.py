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
from bson import ObjectId


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
    """Create new deposit request"""
    try:
        # Validate minimum deposit amount
        if deposit_data.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )

        # Create deposit with current user's ID
        deposit = await create_deposit(
            amount=deposit_data.amount,
            reference=deposit_data.reference,
            user_id=str(current_user.id)
        )
        return deposit

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Deposit creation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create deposit request"
        )


@router.get("/{deposit_id}", response_model=Deposit)
async def read_deposit(
    deposit_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get specific deposit by ID"""
    try:
        if not ObjectId.is_valid(deposit_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid deposit ID format"
            )

        deposit = await get_deposit_by_id(deposit_id)
        if not deposit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deposit not found"
            )

        # Authorization check
        if current_user.role != "admin" and str(deposit.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this deposit"
            )

        return deposit

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching deposit: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

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
    """Approve deposit request - Admin only"""
    try:
        if not ObjectId.is_valid(deposit_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid deposit ID format"
            )

        deposit = await approve_deposit(deposit_id)
        if not deposit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending deposit not found or already processed"
            )

        return deposit

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deposit approval error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve deposit"
        )

@router.post("/{deposit_id}/reject", response_model=Deposit)
async def reject_deposit_endpoint(
    deposit_id: str,
    current_user: User = Depends(get_admin_user)
):
    deposit = await reject_deposit(deposit_id)
    if deposit is None:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return deposit
