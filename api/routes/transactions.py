from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from api.deps import get_current_active_user, get_admin_user
from db.models import Transaction, User, TransactionCreate
from services.transaction_service import (
    get_transaction_by_id,
    get_transactions,
    get_user_transactions,
    create_transaction
)
from services.user_service import update_user_balance
import logging
from bson import ObjectId
from datetime import datetime

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/", response_model=List[Transaction])
async def read_transactions(
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(get_admin_user)
):
    """Get all transactions (admin only)"""
    transactions = await get_transactions(skip, limit)
    return transactions


# @router.get("/user/{user_id}", response_model=List[Transaction])
# async def read_user_transactions(
#         user_id: str,
#         skip: int = 0,
#         limit: int = 100,
#         current_user: User = Depends(get_admin_user)
# ):
#     """Get transactions for specific user (admin only)"""
#     transactions = await get_user_transactions(user_id, skip, limit)
#     return transactions


# @router.get("/me", response_model=List[Transaction])
# async def read_my_transactions(
#         skip: int = 0,
#         limit: int = 100,
#         current_user: User = Depends(get_current_active_user)
# ):
#     """Get current user's transactions"""
#     transactions = await get_user_transactions(str(current_user.id), skip, limit)
#     return transactions



@router.get("/{transaction_id}", response_model=Transaction)
async def read_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get specific transaction by ID.
    Users can only access their own transactions unless they are admins.
    """
    try:
        # Validate transaction ID format
        if not ObjectId.is_valid(transaction_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid transaction ID format"
            )

        # Get transaction from database
        transaction = await get_transaction_by_id(transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        # Verify ownership (unless admin)
        if current_user.role != "admin" and str(transaction.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this transaction"
            )

        return transaction

    except HTTPException:
        # Re-raise HTTP exceptions we created
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching transaction {transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/user/{user_id}", response_model=List[Transaction])
async def read_user_transactions(
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(get_admin_user)
):
    """Get transactions for specific user (admin only)"""
    transactions = await get_user_transactions(user_id, skip, limit)
    return transactions

@router.get("/me/all", response_model=List[Transaction])
async def read_my_transactions(
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(get_current_active_user)
):
    """Get current user's transactions"""
    transactions = await get_user_transactions(str(current_user.id), skip, limit)
    return transactions

@router.post("/", response_model=Transaction)
async def create_new_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_admin_user)
):
    """Create new transaction (admin only)"""
    try:
        transaction = await create_transaction(transaction_data)
        return transaction
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Internal server error creating transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/game", response_model=Transaction)
async def create_game_transaction(
        transaction_data: TransactionCreate,
        current_user: User = Depends(get_current_active_user)
):
    """Record a game transaction"""
    try:
        # Set automatic fields
        transaction_data.user_id = str(current_user.id)
        transaction_data.timestamp = datetime.utcnow()

        # Validate required fields
        if transaction_data.type != "game":
            raise ValueError("Transaction type must be 'game'")

        if transaction_data.amount <= 0:
            raise ValueError("Amount must be positive")

        logger.info(f"Creating game transaction: {transaction_data}")

        # Create the transaction
        transaction = await create_transaction(transaction_data)

        return transaction

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Transaction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
# @router.post("/", response_model=Transaction)
# async def create_new_transaction(
#     transaction_data: TransactionCreate,
#     current_user: User = Depends(get_admin_user)
# ):
#     """Create new transaction (admin only)"""
#     try:
#         transaction = await create_transaction(transaction_data)
#         return transaction
#     except ValueError as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(e),
#         )
#     except Exception as e:
#         logger.error(f"Internal server error creating transaction: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error",
#         )