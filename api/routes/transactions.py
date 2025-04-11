from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from api.deps import get_current_active_user, get_admin_user
from db.database import get_database
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
from motor.motor_asyncio import AsyncIOMotorDatabase as Database

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
        current_user: User = Depends(get_current_active_user),
        db: Database = Depends(get_database)
):
    """Record a game transaction and update balance atomically"""
    async with await db.client.start_session() as session:
        try:
            async with session.start_transaction():
                # Set automatic fields
                transaction_data.user_id = str(current_user.id)
                transaction_data.timestamp = datetime.utcnow()

                # Create the transaction document
                transaction_dict = {
                    "_id": ObjectId(),
                    "user_id": ObjectId(transaction_data.user_id),
                    "type": transaction_data.type,
                    "amount": transaction_data.amount,
                    "timestamp": transaction_data.timestamp,
                    "reference": transaction_data.reference
                }

                # Add optional fields
                if transaction_data.game_id:
                    transaction_dict["game_id"] = ObjectId(transaction_data.game_id)
                if transaction_data.game_name:
                    transaction_dict["game_name"] = transaction_data.game_name
                if transaction_data.result:
                    transaction_dict["result"] = transaction_data.result
                if transaction_data.payout:
                    transaction_dict["payout"] = transaction_data.payout

                # Insert the transaction
                await db.transactions.insert_one(transaction_dict, session=session)

                # Calculate balance change
                balance_change = -transaction_data.amount  # Deduct the stake
                if transaction_data.result == "win":
                    balance_change += transaction_data.payout

                # Update user balance
                await db.users.update_one(
                    {"_id": ObjectId(current_user.id)},
                    {"$inc": {"balance": balance_change}},
                    session=session
                )

                # Convert ObjectIds to strings for the response
                transaction_dict["_id"] = str(transaction_dict["_id"])
                transaction_dict["user_id"] = str(transaction_dict["user_id"])
                if "game_id" in transaction_dict:
                    transaction_dict["game_id"] = str(transaction_dict["game_id"])

                return Transaction.model_validate(transaction_dict)

        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process transaction"
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