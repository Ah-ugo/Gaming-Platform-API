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
    """Get deposit by ID with proper error handling"""
    try:
        if not deposit_id or not ObjectId.is_valid(deposit_id):
            raise ValueError("Invalid deposit ID")

        db = get_database()
        deposit_data = await db.deposits.find_one({"_id": ObjectId(deposit_id)})

        if not deposit_data:
            return None

        # Convert ObjectId to string for Pydantic model
        deposit_data["_id"] = str(deposit_data["_id"])
        return Deposit.model_validate(deposit_data)

    except (InvalidId, ValueError) as e:
        logger.error(f"Invalid deposit ID: {deposit_id} - {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error getting deposit {deposit_id}: {str(e)}")
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


async def create_deposit(deposit_data: DepositCreate) -> Deposit:
    """Create new deposit with comprehensive error handling"""
    db = get_database()

    try:
        # Create deposit document
        deposit_dict = {
            **deposit_data.dict(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": DepositStatus.PENDING.value
        }

        # Insert document
        result = await db.deposits.insert_one(deposit_dict)
        if not result.inserted_id:
            raise ValueError("Failed to create deposit - no ID returned")

        # Add retry logic for eventual consistency
        max_retries = 3
        for attempt in range(max_retries):
            try:
                created_deposit = await get_deposit_by_id(str(result.inserted_id))
                if created_deposit:
                    return created_deposit
                await asyncio.sleep(0.1 * (attempt + 1))
            except Exception as e:
                logger.warning(f"Retry {attempt + 1} failed: {str(e)}")

        raise ValueError("Failed to fetch created deposit after multiple attempts")

    except Exception as e:
        logger.error(f"Deposit creation error: {str(e)}")
        raise ValueError(f"Failed to create deposit: {str(e)}")

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

        # Get deposit document directly (outside transaction)
        deposit_doc = await db.deposits.find_one({
            "_id": ObjectId(deposit_id),
            "status": DepositStatus.PENDING
        })
        if not deposit_doc:
            logger.error(f"Pending deposit not found: {deposit_id}")
            return None

        # Convert to string for user_id
        user_id = str(deposit_doc["user_id"])
        amount = deposit_doc["amount"]
        reference = deposit_doc["reference"]

        # Start a session for atomic operations
        session = await db.client.start_session()
        try:
            async with session.start_transaction():
                # 1. Update deposit status
                update_result = await db.deposits.update_one(
                    {"_id": ObjectId(deposit_id)},
                    {"$set": {
                        "status": DepositStatus.APPROVED,
                        "updated_at": datetime.utcnow()
                    }},
                    session=session
                )

                if not update_result.modified_count:
                    raise ValueError("Deposit status update failed")

                # 2. Update user balance
                user_updated = await update_user_balance(user_id, amount)
                if not user_updated:
                    raise ValueError("User balance update failed")

                # 3. Create transaction record
                transaction_data = TransactionCreate(
                    user_id=user_id,
                    type=TransactionType.DEPOSIT,
                    amount=amount,
                    reference=reference
                )

                # Explicitly generate new ObjectId for transaction
                transaction_id = ObjectId()
                transaction_dict = {
                    "_id": transaction_id,
                    **transaction_data.dict(),
                    "timestamp": datetime.utcnow()
                }

                # Insert with explicit ID
                insert_result = await db.transactions.insert_one(
                    transaction_dict,
                    session=session
                )

                if not insert_result.inserted_id:
                    raise ValueError("Transaction creation failed")

                await session.commit_transaction()
                logger.info(f"Deposit {deposit_id} approved successfully")

                # Return updated deposit
                return Deposit.model_validate({
                    **deposit_doc,
                    "_id": deposit_id,
                    "status": DepositStatus.APPROVED,
                    "updated_at": datetime.utcnow()
                })

        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            if session and session.in_transaction:
                await session.abort_transaction()
            return None
        finally:
            if session:
                await session.end_session()

    except Exception as e:
        logger.error(f"Error approving deposit: {str(e)}")
        return None


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
