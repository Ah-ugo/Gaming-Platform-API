from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from db.database import get_database
from db.models import Deposit, DepositCreate, DepositStatus, DepositUpdate, TransactionCreate, TransactionType
from services.user_service import update_user_balance
from services.transaction_service import create_transaction
import asyncio
import logging


logger = logging.getLogger(__name__)


async def get_deposit_by_id(deposit_id: str) -> Optional[Deposit]:
    """Get deposit by ID with proper ObjectId handling"""
    try:
        # Validate ID format first
        if not ObjectId.is_valid(deposit_id):
            raise ValueError("Invalid deposit ID format")

        db = get_database()
        doc = await db.deposits.find_one({"_id": ObjectId(deposit_id)})

        if not doc:
            return None

        # Convert ObjectId fields to strings
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("user_id"), ObjectId):
            doc["user_id"] = str(doc["user_id"])

        # Add debug logging
        logger.debug(f"Retrieved deposit document: {doc}")

        return Deposit.model_validate(doc)

    except Exception as e:
        logger.error(f"Error getting deposit {deposit_id}: {str(e)}", exc_info=True)
        return None



async def get_deposits(skip: int = 0, limit: int = 100) -> List[Deposit]:
    """Get paginated list of deposits with proper model validation"""
    try:
        db = get_database()
        deposits = []
        cursor = db.deposits.find().sort("created_at", -1).skip(skip).limit(limit)

        async for deposit_doc in cursor:
            try:
                # Convert ObjectId to string
                deposit_doc["_id"] = str(deposit_doc["_id"])
                # Convert user_id to string if it exists
                if "user_id" in deposit_doc:
                    deposit_doc["user_id"] = str(deposit_doc["user_id"])
                # Validate against Deposit model
                deposit = Deposit.model_validate(deposit_doc)
                deposits.append(deposit)
            except Exception as e:
                logger.error(f"Skipping invalid deposit document: {str(e)}")
                logger.debug(f"Problematic document: {deposit_doc}")

        return deposits

    except Exception as e:
        logger.error(f"Error getting deposits: {str(e)}")
        return []


async def get_pending_deposits() -> List[Deposit]:
    """Get list of pending deposits with proper model validation"""
    try:
        db = get_database()
        deposits = []
        cursor = db.deposits.find({"status": DepositStatus.PENDING}).sort("created_at", -1)

        async for deposit_doc in cursor:
            try:
                # Convert ObjectId to string
                deposit_doc["_id"] = str(deposit_doc["_id"])
                # Convert user_id to string if it exists
                if "user_id" in deposit_doc:
                    deposit_doc["user_id"] = str(deposit_doc["user_id"])
                # Validate against Deposit model
                deposit = Deposit.model_validate(deposit_doc)
                deposits.append(deposit)
            except Exception as e:
                logger.error(f"Skipping invalid deposit document: {str(e)}")
                logger.debug(f"Problematic document: {deposit_doc}")

        return deposits

    except Exception as e:
        logger.error(f"Error getting pending deposits: {str(e)}")
        return []


async def create_deposit(
        amount: float,
        reference: str,
        user_id: str
) -> Deposit:
    """Create new deposit with comprehensive error handling"""
    db = get_database()
    session = None

    try:
        # Validate user_id format
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID format")

        # Start atomic session
        session = await db.client.start_session()

        async with session.start_transaction():
            # Create deposit document
            deposit_dict = {
                "user_id": ObjectId(user_id),
                "amount": amount,
                "reference": reference,
                "status": DepositStatus.PENDING.value,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Insert document
            result = await db.deposits.insert_one(deposit_dict, session=session)
            if not result.inserted_id:
                raise ValueError("Failed to create deposit - no ID returned")

            # Create transaction record
            transaction_data = {
                "_id": ObjectId(),
                "user_id": ObjectId(user_id),
                "type": TransactionType.DEPOSIT,
                "amount": amount,
                "reference": reference,
                "status": "pending",
                "timestamp": datetime.utcnow()
            }

            await db.transactions.insert_one(transaction_data, session=session)

            await session.commit_transaction()

            # Return created deposit
            deposit_dict["_id"] = str(result.inserted_id)
            deposit_dict["user_id"] = user_id
            return Deposit.model_validate(deposit_dict)

    except Exception as e:
        logger.error(f"Deposit creation failed: {str(e)}")
        if session and session.in_transaction:
            await session.abort_transaction()
        raise ValueError(f"Failed to create deposit: {str(e)}")
    finally:
        if session:
            await session.end_session()



async def update_deposit(deposit_id: str, deposit_data: DepositUpdate) -> Optional[Deposit]:
    db = get_database()

    # Remove None values
    update_data = {k: v for k, v in deposit_data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    # Update deposit
    result = await db.deposits.update_one(
        {"_id": ObjectId(deposit_id)},
        {"$set": update_data}
    )

    if result.modified_count:
        return await get_deposit_by_id(deposit_id)
    return None


async def approve_deposit(deposit_id: str) -> Optional[Deposit]:
    """Approve deposit with comprehensive error handling"""
    db = get_database()
    session = None

    try:
        # Validate deposit_id format
        if not ObjectId.is_valid(deposit_id):
            logger.error(f"Invalid deposit ID format: {deposit_id}")
            return None

        # Get deposit document
        deposit_doc = await db.deposits.find_one({
            "_id": ObjectId(deposit_id),
            "status": DepositStatus.PENDING
        })
        if not deposit_doc:
            logger.error(f"Pending deposit not found: {deposit_id}")
            return None

        # Convert user_id to string
        user_id = str(deposit_doc["user_id"])
        amount = deposit_doc["amount"]
        reference = deposit_doc["reference"]

        # Start atomic session
        session = await db.client.start_session()
        async with session.start_transaction():
            # 1. Update deposit status
            await db.deposits.update_one(
                {"_id": ObjectId(deposit_id)},
                {"$set": {
                    "status": DepositStatus.APPROVED,
                    "updated_at": datetime.utcnow()
                }},
                session=session
            )

            # 2. Update user balance
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"balance": amount}},
                session=session
            )

            # 3. Create transaction record
            transaction_data = {
                "_id": ObjectId(),
                "user_id": ObjectId(user_id),
                "type": TransactionType.DEPOSIT,
                "amount": amount,
                "reference": reference,
                "status": "completed",
                "timestamp": datetime.utcnow()
            }
            await db.transactions.insert_one(transaction_data, session=session)

            await session.commit_transaction()

            # Return updated deposit
            deposit_doc["_id"] = deposit_id
            deposit_doc["user_id"] = user_id
            deposit_doc["status"] = DepositStatus.APPROVED
            deposit_doc["updated_at"] = datetime.utcnow()
            return Deposit.model_validate(deposit_doc)

    except Exception as e:
        logger.error(f"Deposit approval failed: {str(e)}", exc_info=True)
        if session and session.in_transaction:
            await session.abort_transaction()
        return None
    finally:
        if session:
            await session.end_session()



async def reject_deposit(deposit_id: str) -> Optional[Deposit]:
    db = get_database()

    # Get deposit
    deposit = await get_deposit_by_id(deposit_id)
    if not deposit or deposit.status != DepositStatus.PENDING:
        return None

    # Update deposit status
    update_data = {
        "status": DepositStatus.REJECTED,
        "updated_at": datetime.utcnow()
    }

    result = await db.deposits.update_one(
        {"_id": ObjectId(deposit_id)},
        {"$set": update_data}
    )

    if result.modified_count:
        return await get_deposit_by_id(deposit_id)
    return None
