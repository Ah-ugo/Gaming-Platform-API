from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from api.deps import get_current_active_user, get_admin_user
from db.database import get_database
from db.models import Withdrawal, WithdrawalCreate, WithdrawalUpdate, User
from services.withdrawal_service import (
    get_withdrawal_by_id,
    get_withdrawals,
    get_pending_withdrawals,
    create_withdrawal,
    approve_withdrawal,
    reject_withdrawal, process_withdrawal
)
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[Withdrawal])
async def read_withdrawals(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user)
):
    """Get all withdrawals (admin only)"""
    withdrawals = await get_withdrawals(skip, limit)
    return withdrawals

@router.get("/pending", response_model=List[Withdrawal])
async def read_pending_withdrawals(
    current_user: User = Depends(get_admin_user)
):
    """Get pending withdrawals (admin only)"""
    withdrawals = await get_pending_withdrawals()
    return withdrawals

@router.get("/{withdrawal_id}", response_model=Withdrawal)
async def read_withdrawal(
    withdrawal_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get specific withdrawal by ID"""
    try:
        if not ObjectId.is_valid(withdrawal_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid withdrawal ID format"
            )

        withdrawal = await get_withdrawal_by_id(withdrawal_id)
        if not withdrawal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Withdrawal not found"
            )

        # Users can only view their own withdrawals unless admin
        if current_user.role != "admin" and str(withdrawal.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this withdrawal"
            )

        return withdrawal

    except Exception as e:
        logger.error(f"Error fetching withdrawal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/", response_model=Withdrawal)
async def create_withdrawal_request(
        withdrawal_data: WithdrawalCreate,
        current_user: User = Depends(get_current_active_user)
):
    """Create new withdrawal request with bank details"""
    try:
        # Validate minimum withdrawal amount
        if withdrawal_data.amount < 10:  # Example minimum
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum withdrawal amount is $10"
            )

        withdrawal = await create_withdrawal(
            amount=withdrawal_data.amount,
            bank_account=withdrawal_data.bank_account,
            reference=withdrawal_data.reference,
            user_id=str(current_user.id)
        )
        return withdrawal

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Withdrawal creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create withdrawal request"
        )


@router.post("/{withdrawal_id}/process", response_model=Withdrawal)
async def process_withdrawal_request(
        withdrawal_id: str,
        action: WithdrawalUpdate,
        current_user: User = Depends(get_admin_user)
):
    """Process withdrawal request (approve/reject) - Admin only"""
    try:
        withdrawal = await process_withdrawal(
            withdrawal_id=withdrawal_id,
            status=action.status,
            admin_notes=action.admin_notes,
            admin_id=str(current_user.id)
        )

        if not withdrawal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending withdrawal not found"
            )

        return withdrawal

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Withdrawal processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process withdrawal"
        )

@router.post("/{withdrawal_id}/approve", response_model=Withdrawal)
async def approve_withdrawal_request(
    withdrawal_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Approve a withdrawal request (admin only)"""
    try:
        withdrawal = await approve_withdrawal(withdrawal_id)
        if not withdrawal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending withdrawal not found"
            )
        return withdrawal
    except Exception as e:
        logger.error(f"Error approving withdrawal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/{withdrawal_id}/reject", response_model=Withdrawal)
async def reject_withdrawal_request(
    withdrawal_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Reject a withdrawal request (admin only)"""
    try:
        withdrawal = await reject_withdrawal(withdrawal_id)
        if not withdrawal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending withdrawal not found"
            )
        return withdrawal
    except Exception as e:
        logger.error(f"Error rejecting withdrawal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )