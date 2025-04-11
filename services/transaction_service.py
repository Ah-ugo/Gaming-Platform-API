import asyncio
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from db.database import get_database
from db.models import Transaction, TransactionCreate
import logging

logger = logging.getLogger(__name__)


async def get_transaction_by_id(transaction_id: str) -> Optional[Transaction]:
    """Get transaction by ID with proper model validation"""
    try:
        if not transaction_id or not ObjectId.is_valid(transaction_id):
            logger.error(f"Invalid transaction ID format: {transaction_id}")
            return None

        db = get_database()
        doc = await db.transactions.find_one({"_id": ObjectId(transaction_id)})
        if not doc:
            return None

        # Convert all ObjectId fields to strings
        doc["_id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        if "game_id" in doc and doc["game_id"]:
            doc["game_id"] = str(doc["game_id"])

        # Validate against Transaction model
        return Transaction.model_validate(doc)

    except Exception as e:
        logger.error(f"Error getting transaction {transaction_id}: {str(e)}")
        return None


async def get_transactions(skip: int = 0, limit: int = 100) -> List[Transaction]:
    """Get paginated list of transactions"""
    try:
        db = get_database()
        transactions = []
        cursor = db.transactions.find().sort("timestamp", -1).skip(skip).limit(limit)

        async for doc in cursor:
            try:
                # Convert ObjectIds to strings
                doc["_id"] = str(doc["_id"])
                if "user_id" in doc:
                    doc["user_id"] = str(doc["user_id"])
                if "game_id" in doc and doc["game_id"]:
                    doc["game_id"] = str(doc["game_id"])

                transactions.append(Transaction.model_validate(doc))
            except Exception as e:
                logger.error(f"Skipping invalid transaction: {str(e)}")

        return transactions

    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        return []


async def get_user_transactions(user_id: str, skip: int = 0, limit: int = 100) -> List[Transaction]:
    """Get user's transactions with proper model validation"""
    try:
        if not user_id or not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID format")

        db = get_database()
        transactions = []
        cursor = db.transactions.find({"user_id": ObjectId(user_id)}).sort("timestamp", -1).skip(skip).limit(limit)

        async for doc in cursor:
            try:
                # Convert all ObjectId fields to strings
                doc["_id"] = str(doc["_id"])
                doc["user_id"] = str(doc["user_id"])
                if "game_id" in doc and doc["game_id"]:
                    doc["game_id"] = str(doc["game_id"])

                # Validate against Transaction model
                transaction = Transaction.model_validate(doc)
                transactions.append(transaction)
            except Exception as e:
                logger.error(f"Skipping invalid transaction document: {str(e)}")
                logger.debug(f"Problematic document: {doc}")

        return transactions

    except Exception as e:
        logger.error(f"Error getting user transactions: {str(e)}")
        return []

async def create_transaction(transaction_data: TransactionCreate) -> Transaction:
    """Create new transaction with comprehensive error handling"""
    db = get_database()

    try:
        # Validate input IDs
        if not ObjectId.is_valid(transaction_data.user_id):
            raise ValueError("Invalid user ID format")
        if transaction_data.game_id and not ObjectId.is_valid(transaction_data.game_id):
            raise ValueError("Invalid game ID format")

        # Prepare transaction document with explicit _id
        transaction_id = ObjectId()
        transaction_dict = {
            "_id": transaction_id,
            "user_id": ObjectId(transaction_data.user_id),
            "type": transaction_data.type,
            "amount": transaction_data.amount,
            "timestamp": datetime.utcnow(),
            "reference": transaction_data.reference
        }

        # Add optional fields if they exist
        if transaction_data.game_id:
            transaction_dict["game_id"] = ObjectId(transaction_data.game_id)
        if transaction_data.game_name:
            transaction_dict["game_name"] = transaction_data.game_name
        if transaction_data.result:
            transaction_dict["result"] = transaction_data.result
        if transaction_data.payout:
            transaction_dict["payout"] = transaction_data.payout

        # Insert document with explicit ID
        result = await db.transactions.insert_one(transaction_dict)
        if not result.acknowledged:
            raise ValueError("Transaction creation failed - not acknowledged")

        # Add retry logic for eventual consistency
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Get the document using our known ID
                created_doc = await db.transactions.find_one({"_id": transaction_id})
                if created_doc:
                    # Convert ObjectIds to strings
                    created_doc["_id"] = str(created_doc["_id"])
                    created_doc["user_id"] = str(created_doc["user_id"])
                    if "game_id" in created_doc and created_doc["game_id"]:
                        created_doc["game_id"] = str(created_doc["game_id"])

                    return Transaction.model_validate(created_doc)

                await asyncio.sleep(0.1 * (attempt + 1))
            except Exception as e:
                logger.warning(f"Retry {attempt + 1} failed: {str(e)}")

        raise ValueError("Failed to fetch created transaction after multiple attempts")

    except ValueError as ve:
        logger.error(f"Validation error creating transaction: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Transaction creation error: {str(e)}")
        raise ValueError(f"Failed to create transaction: {str(e)}")