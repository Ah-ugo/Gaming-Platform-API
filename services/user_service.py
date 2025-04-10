import asyncio
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from core.security import get_password_hash, verify_password
from db.database import get_database
from db.models import User, UserCreate, UserInDB, UserUpdate
import logging

logger = logging.getLogger(__name__)


def validate_object_id(id_str: str) -> ObjectId:
    """Helper function to validate and convert string to ObjectId"""
    try:
        return ObjectId(id_str)
    except InvalidId as e:
        logger.error(f"Invalid ObjectId: {id_str}")
        raise ValueError(f"Invalid ID format: {id_str}") from e


async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user by email with proper error handling"""
    try:
        db = get_database()
        user_data = await db.users.find_one({"email": email})
        return UserInDB(**user_data) if user_data else None
    except Exception as e:
        logger.error(f"Error getting user by email {email}: {str(e)}")
        return None


# async def get_user_by_id(user_id: str) -> Optional[User]:
#     """Get user by ID with proper ObjectId validation"""
#     try:
#         db = get_database()
#         obj_id = validate_object_id(user_id)
#         user_data = await db.users.find_one({"_id": obj_id})
#         return User(**user_data) if user_data else None
#     except ValueError as ve:
#         logger.error(f"Validation error for user ID {user_id}: {str(ve)}")
#         return None
#     except Exception as e:
#         logger.error(f"Error getting user by ID {user_id}: {str(e)}")
#         return None

async def get_user_by_id(user_id: str) -> Optional[User]:
    try:
        db = get_database()
        # Convert string ID to ObjectId for query
        obj_id = ObjectId(user_id)
        user_data = await db.users.find_one({"_id": obj_id})

        if not user_data:
            return None

        # Convert ObjectId to string for Pydantic model
        user_data["_id"] = str(user_data["_id"])
        return User.model_validate(user_data)
    except Exception as e:
        logger.error(f"Error getting user by ID {user_id}: {str(e)}")
        return None


async def get_users(skip: int = 0, limit: int = 100) -> List[User]:
    """Get paginated list of users with proper model validation"""
    try:
        db = get_database()
        users = []
        cursor = db.users.find().skip(skip).limit(limit)

        async for user_doc in cursor:
            try:
                # Convert ObjectId to string
                user_doc["_id"] = str(user_doc["_id"])

                # Validate against User model
                user = User.model_validate(user_doc)
                users.append(user)
            except Exception as e:
                logger.error(f"Skipping invalid user document: {str(e)}")
                logger.debug(f"Problematic document: {user_doc}")

        return users

    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        return []

# async def create_user(user_data: UserCreate) -> User:
#     db = get_database()
#
#     try:
#         # Check for existing user
#         if await db.users.find_one({"email": user_data.email}):
#             raise ValueError("Email already registered")
#
#         # Create user document
#         user_dict = {
#             "email": user_data.email,
#             "first_name": user_data.first_name,
#             "last_name": user_data.last_name,
#             "is_active": user_data.is_active,
#             "role": user_data.role,
#             "hashed_password": get_password_hash(user_data.password),
#             "balance": 0.0,
#             "created_at": datetime.utcnow(),
#             "updated_at": datetime.utcnow()
#         }
#
#         # Insert document
#         result = await db.users.insert_one(user_dict)
#         if not result.inserted_id:
#             raise ValueError("Insert operation failed")
#
#         # Fetch and return the created user
#         created_user = await db.users.find_one({"_id": result.inserted_id})
#         if not created_user:
#             raise ValueError("User not found after creation")
#
#         # Convert ObjectId to string
#         created_user["id"] = str(created_user["_id"])
#         return User.model_validate(created_user)
#
#     except Exception as e:
#         logger.error(f"Registration error: {str(e)}")
#         raise ValueError(f"User registration failed: {str(e)}")

async def create_user(user_data: UserCreate) -> User:
    db = get_database()

    try:
        # Check for existing user
        if await db.users.find_one({"email": user_data.email}):
            raise ValueError("Email already registered")

        # Create user document with all required fields
        user_dict = {
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "is_active": user_data.is_active,
            "role": user_data.role,
            "hashed_password": get_password_hash(user_data.password),
            "balance": 0.0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Insert document
        result = await db.users.insert_one(user_dict)
        if not result.inserted_id:
            raise ValueError("Insert operation failed")

        # Fetch the created document
        created_user = await db.users.find_one({"_id": result.inserted_id})
        if not created_user:
            raise ValueError("User not found after creation")

        # Prepare document for Pydantic model
        user_doc = {
            "_id": str(created_user["_id"]),  # Convert ObjectId to string
            "email": created_user["email"],
            "first_name": created_user["first_name"],
            "last_name": created_user["last_name"],
            "is_active": created_user["is_active"],
            "role": created_user["role"],
            "balance": created_user["balance"],
            "created_at": created_user["created_at"],
            "updated_at": created_user["updated_at"]
        }

        # Validate against User model
        try:
            return User.model_validate(user_doc)
        except Exception as model_err:
            logger.error(f"Model validation failed: {model_err}")
            logger.error(f"Document causing error: {user_doc}")
            raise ValueError("User created but model validation failed")

    except ValueError as ve:
        logger.error(f"Validation error creating user: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating user: {str(e)}")
        raise ValueError("Failed to create user") from e


async def authenticate_user(email: str, password: str) -> Optional[User]:
    try:
        # Get the raw document first
        db = get_database()
        user_data = await db.users.find_one({"email": email})

        if not user_data:
            logger.debug(f"No user found with email: {email}")
            return None

        if not user_data.get("is_active", True):
            logger.debug(f"User {email} is inactive")
            return None

        # Verify password
        if not verify_password(password, user_data["hashed_password"]):
            logger.debug(f"Password verification failed for {email}")
            return None

        # Convert to User model
        user_data["_id"] = str(user_data["_id"])  # Convert ObjectId to string
        return User.model_validate(user_data)

    except Exception as e:
        logger.error(f"Authentication error for {email}: {str(e)}")
        return None



async def update_user(user_id: str, user_data: UserUpdate) -> Optional[User]:
    """Update user with comprehensive error handling"""
    try:
        db = get_database()
        obj_id = validate_object_id(user_id)

        # Prepare update data
        update_data = {k: v for k, v in user_data.dict().items() if v is not None}
        if not update_data:
            raise ValueError("No valid fields provided for update")
        update_data["updated_at"] = datetime.utcnow()

        # Perform update
        result = await db.users.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            logger.warning(f"No changes made for user {user_id}")
            return None

        return await get_user_by_id(user_id)

    except ValueError as ve:
        logger.error(f"Validation error updating user {user_id}: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        raise ValueError("Failed to update user") from e


async def delete_user(user_id: str) -> Optional[User]:
    """Delete user with proper error handling"""
    try:
        db = get_database()
        obj_id = validate_object_id(user_id)

        # Get user before deletion
        user = await get_user_by_id(user_id)
        if not user:
            return None

        # Delete user
        result = await db.users.delete_one({"_id": obj_id})

        if result.deleted_count == 0:
            logger.warning(f"No user deleted for ID {user_id}")
            return None

        return user

    except ValueError as ve:
        logger.error(f"Validation error deleting user {user_id}: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise ValueError("Failed to delete user") from e


async def update_user_balance(
        user_id: str,
        amount: float
) -> bool:
    """Update user balance without session support"""
    try:
        db = get_database()

        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID format")

        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"balance": amount}}
        )

        return result.modified_count == 1

    except Exception as e:
        logger.error(f"Error updating balance for user {user_id}: {str(e)}")
        return False