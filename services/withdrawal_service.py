from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from db.database import get_database
from db.models import (
    Withdrawal,
    WithdrawalCreate,
    WithdrawalStatus,
    WithdrawalUpdate,
    TransactionCreate,
    TransactionType, BankAccount
)
from services.user_service import update_user_balance
from services.transaction_service import create_transaction
import asyncio
import logging

logger = logging.getLogger(__name__)


async def get_withdrawal_by_id(withdrawal_id: str) -> Optional[Withdrawal]:
    """Get withdrawal by ID with proper ObjectId handling"""
    try:
        # Validate ID format first
        if not ObjectId.is_valid(withdrawal_id):
            raise ValueError("Invalid withdrawal ID format")

        db = get_database()
        doc = await db.withdrawals.find_one({"_id": ObjectId(withdrawal_id)})

        if not doc:
            return None

        # Convert ObjectId fields to strings
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("user_id"), ObjectId):
            doc["user_id"] = str(doc["user_id"])

        # Add debug logging
        logger.debug(f"Retrieved withdrawal document: {doc}")

        return Withdrawal.model_validate(doc)

    except Exception as e:
        logger.error(f"Error getting withdrawal {withdrawal_id}: {str(e)}", exc_info=True)
        return None


async def get_withdrawals(skip: int = 0, limit: int = 100) -> List[Withdrawal]:
    """Get paginated list of withdrawals"""
    try:
        db = get_database()
        withdrawals = []
        cursor = db.withdrawals.find().sort("created_at", -1).skip(skip).limit(limit)

        async for doc in cursor:
            try:
                # Add debug logging
                logger.debug(f"Raw withdrawal document: {doc}")

                # Convert ObjectId to string
                doc["_id"] = str(doc["_id"])
                doc["user_id"] = str(doc["user_id"])

                # Validate against model
                withdrawal = Withdrawal.model_validate(doc)
                withdrawals.append(withdrawal)
            except Exception as e:
                logger.error(f"Skipping invalid withdrawal document: {str(e)}")
                logger.debug(f"Problematic document: {doc}")

        # Add debug logging
        logger.debug(f"Found {len(withdrawals)} withdrawals")
        return withdrawals

    except Exception as e:
        logger.error(f"Error getting withdrawals: {str(e)}", exc_info=True)
        return []


# In withdrawal_service.py
async def get_pending_withdrawals() -> List[Withdrawal]:
    """Get list of pending withdrawals with debug logging"""
    try:
        db = get_database()
        withdrawals = []

        # Add collection verification
        collection_names = await db.list_collection_names()
        logger.debug(f"Available collections: {collection_names}")

        if "withdrawals" not in collection_names:
            logger.error("Withdrawals collection does not exist!")
            return []

        # Count documents for debugging
        total_count = await db.withdrawals.count_documents({})
        pending_count = await db.withdrawals.count_documents({"status": "pending"})
        logger.debug(f"Total withdrawals: {total_count}, Pending: {pending_count}")

        cursor = db.withdrawals.find({"status": "pending"}).sort("created_at", -1)

        async for doc in cursor:
            try:
                logger.debug(f"Raw document: {doc}")

                # Convert ObjectIds
                doc["_id"] = str(doc["_id"])
                doc["user_id"] = str(doc["user_id"])

                # Validate model
                withdrawal = Withdrawal.model_validate(doc)
                withdrawals.append(withdrawal)
            except Exception as e:
                logger.error(f"Document validation failed: {str(e)}", exc_info=True)

        logger.debug(f"Found {len(withdrawals)} pending withdrawals")
        return withdrawals

    except Exception as e:
        logger.error(f"Error in get_pending_withdrawals: {str(e)}", exc_info=True)
        return []




async def create_withdrawal(
        amount: float,
        bank_account: BankAccount,
        reference: Optional[str],
        user_id: str
) -> Withdrawal:
    """Create new withdrawal request with bank details"""
    db = get_database()
    session = None

    try:
        # Validate user_id format
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID format")

        # Start atomic session
        session = await db.client.start_session()

        async with session.start_transaction():
            # 1. Verify user has sufficient balance
            user = await db.users.find_one(
                {"_id": ObjectId(user_id)},
                session=session
            )
            if not user:
                raise ValueError("User not found")

            if user["balance"] < amount:
                raise ValueError("Insufficient balance")

            # 2. Create withdrawal record
            withdrawal_dict = {
                "user_id": ObjectId(user_id),
                "amount": amount,
                "bank_account": bank_account.dict(),
                "status": WithdrawalStatus.PENDING,
                "reference": reference or f"WDR-{datetime.utcnow().timestamp()}",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await db.withdrawals.insert_one(
                withdrawal_dict,
                session=session
            )

            if not result.inserted_id:
                raise ValueError("Withdrawal creation failed")

            # 3. Reserve funds by deducting from available balance
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"balance": -amount}},
                session=session
            )

            # 4. Record transaction
            transaction_data = {
                "_id": ObjectId(),
                "user_id": ObjectId(user_id),
                "type": TransactionType.WITHDRAWAL,
                "amount": amount,
                "reference": withdrawal_dict["reference"],
                "status": "pending",
                "timestamp": datetime.utcnow()
            }

            await db.transactions.insert_one(
                transaction_data,
                session=session
            )

            await session.commit_transaction()

            # Return created withdrawal
            withdrawal_dict["_id"] = str(result.inserted_id)
            withdrawal_dict["user_id"] = user_id
            return Withdrawal.model_validate(withdrawal_dict)

    except Exception as e:
        logger.error(f"Withdrawal creation failed: {str(e)}")
        if session and session.in_transaction:
            await session.abort_transaction()
        raise ValueError(f"Failed to create withdrawal: {str(e)}")
    finally:
        if session:
            await session.end_session()


async def process_withdrawal(
        withdrawal_id: str,
        status: WithdrawalStatus,
        admin_notes: Optional[str] = None,
        admin_id: Optional[str] = None
) -> Optional[Withdrawal]:
    """Admin process withdrawal (approve/reject)"""
    db = get_database()
    session = None

    try:
        if not ObjectId.is_valid(withdrawal_id):
            raise ValueError("Invalid withdrawal ID")

        session = await db.client.start_session()

        async with session.start_transaction():
            # 1. Get and validate withdrawal
            withdrawal = await db.withdrawals.find_one(
                {"_id": ObjectId(withdrawal_id), "status": WithdrawalStatus.PENDING},
                session=session
            )
            if not withdrawal:
                raise ValueError("Pending withdrawal not found")

            user_id = withdrawal["user_id"]
            amount = withdrawal["amount"]

            # 2. Update withdrawal status
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            if admin_notes:
                update_data["admin_notes"] = admin_notes
            if admin_id:
                update_data["processed_by"] = ObjectId(admin_id)

            await db.withdrawals.update_one(
                {"_id": ObjectId(withdrawal_id)},
                {"$set": update_data},
                session=session
            )

            # 3. Update transaction status
            await db.transactions.update_one(
                {"reference": withdrawal["reference"]},
                {"$set": {"status": status.value}},
                session=session
            )

            # 4. If rejected, refund the amount
            if status == WithdrawalStatus.REJECTED:
                await db.users.update_one(
                    {"_id": user_id},
                    {"$inc": {"balance": amount}},
                    session=session
                )

                # Record refund transaction
                refund_tx = {
                    "_id": ObjectId(),
                    "user_id": user_id,
                    "type": TransactionType.DEPOSIT,
                    "amount": amount,
                    "reference": f"REFUND-{withdrawal['reference']}",
                    "status": "completed",
                    "timestamp": datetime.utcnow(),
                    "notes": "Withdrawal refund"
                }
                await db.transactions.insert_one(refund_tx, session=session)

            await session.commit_transaction()

            # Return updated withdrawal
            withdrawal.update(update_data)
            withdrawal["_id"] = str(withdrawal["_id"])
            withdrawal["user_id"] = str(user_id)
            return Withdrawal.model_validate(withdrawal)

    except Exception as e:
        logger.error(f"Withdrawal processing failed: {str(e)}")
        if session and session.in_transaction:
            await session.abort_transaction()
        return None
    finally:
        if session:
            await session.end_session()

async def approve_withdrawal(withdrawal_id: str) -> Optional[Withdrawal]:
    """Approve a pending withdrawal"""
    db = get_database()

    # Update withdrawal status
    result = await db.withdrawals.update_one(
        {"_id": ObjectId(withdrawal_id), "status": WithdrawalStatus.PENDING},
        {"$set": {
            "status": WithdrawalStatus.APPROVED,
            "updated_at": datetime.utcnow()
        }}
    )

    if result.modified_count:
        return await get_withdrawal_by_id(withdrawal_id)
    return None


async def reject_withdrawal(withdrawal_id: str) -> Optional[Withdrawal]:
    """Reject a pending withdrawal and refund the user"""
    db = get_database()
    session = None

    try:
        session = await db.client.start_session()

        async with session.start_transaction():
            # 1. Get withdrawal
            withdrawal = await db.withdrawals.find_one(
                {"_id": ObjectId(withdrawal_id), "status": WithdrawalStatus.PENDING},
                session=session
            )
            if not withdrawal:
                return None

            # 2. Update withdrawal status
            await db.withdrawals.update_one(
                {"_id": ObjectId(withdrawal_id)},
                {"$set": {
                    "status": WithdrawalStatus.REJECTED,
                    "updated_at": datetime.utcnow()
                }},
                session=session
            )

            # 3. Refund user balance
            await db.users.update_one(
                {"_id": withdrawal["user_id"]},
                {"$inc": {"balance": withdrawal["amount"]}},
                session=session
            )

            # 4. Create refund transaction
            transaction_data = TransactionCreate(
                user_id=str(withdrawal["user_id"]),
                type=TransactionType.DEPOSIT,  # Using DEPOSIT for refund
                amount=withdrawal["amount"],
                reference=f"REFUND-{withdrawal['reference']}"
            )

            await db.transactions.insert_one(
                {
                    "_id": ObjectId(),
                    **transaction_data.dict(),
                    "timestamp": datetime.utcnow()
                },
                session=session
            )

            await session.commit_transaction()

            # Return updated withdrawal
            withdrawal["_id"] = str(withdrawal["_id"])
            withdrawal["status"] = WithdrawalStatus.REJECTED
            withdrawal["updated_at"] = datetime.utcnow()
            return Withdrawal.model_validate(withdrawal)

    except Exception as e:
        logger.error(f"Withdrawal rejection failed: {str(e)}")
        if session and session.in_transaction:
            await session.abort_transaction()
        return None
    finally:
        if session:
            await session.end_session()