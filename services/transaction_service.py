from typing import List, Optional
from bson import ObjectId
from db.database import get_database
from db.models import Transaction, TransactionCreate


async def get_transaction_by_id(transaction_id: str) -> Optional[Transaction]:
    db = get_database()
    transaction_data = await db.transactions.find_one({"_id": ObjectId(transaction_id)})
    if transaction_data:
        return Transaction(**transaction_data)
    return None


async def get_transactions(skip: int = 0, limit: int = 100) -> List[Transaction]:
    db = get_database()
    transactions = []
    cursor = db.transactions.find().sort("timestamp", -1).skip(skip).limit(limit)
    async for transaction in cursor:
        transactions.append(Transaction(**transaction))
    return transactions


async def get_user_transactions(user_id: str, skip: int = 0, limit: int = 100) -> List[Transaction]:
    db = get_database()
    transactions = []
    cursor = db.transactions.find({"user_id": ObjectId(user_id)}).sort("timestamp", -1).skip(skip).limit(limit)
    async for transaction in cursor:
        transactions.append(Transaction(**transaction))
    return transactions


async def create_transaction(transaction_data: TransactionCreate) -> Transaction:
    db = get_database()

    transaction = Transaction(**transaction_data.dict())

    result = await db.transactions.insert_one(transaction.dict(by_alias=True))

    # Get the created transaction
    created_transaction = await get_transaction_by_id(str(result.inserted_id))
    return created_transaction
