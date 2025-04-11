from datetime import datetime
from enum import Enum
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, ConfigDict, field_validator
from bson import ObjectId

# Custom ObjectId field for MongoDB
# class PyObjectId(ObjectId):
#     @classmethod
#     def __get_validators__(cls):
#         yield cls.validate
#
#     @classmethod
#     def validate(cls, v):
#         if not ObjectId.is_valid(v):
#             raise ValueError("Invalid ObjectId")
#         return ObjectId(v)
#
#     @classmethod
#     def __modify_schema__(cls, field_schema):
#         field_schema.update(type="string")


def validate_objectid(value: str) -> str:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return value

PyObjectId = Annotated[str, BeforeValidator(validate_objectid)]


# Base model with ID field
class MongoBaseModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}

# User models
class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

class UserBase(BaseModel):
    email: str
    first_name: str
    last_name: str
    is_active: bool = True
    role: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    balance: Optional[float] = None


class UserInDB(UserBase):
    id: PyObjectId = Field(alias="_id")
    hashed_password: str
    balance: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class User(UserBase):
    id: PyObjectId = Field(alias="_id")
    balance: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

# Game models
class GameCategory(str, Enum):
    CARD = "card"
    DICE = "dice"
    WHEEL = "wheel"
    POPULAR = "popular"

class GameBase(BaseModel):
    title: str
    description: str
    min_stake: float
    category: str
    icon: Optional[str] = None
    image_url: Optional[str] = None
    rules: str
    is_active: bool = True


class GameCreate(GameBase):
    pass

class GameUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    min_stake: Optional[float] = None
    category: Optional[GameCategory] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    rules: Optional[str] = None
    is_active: Optional[bool] = None

class Game(GameBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

# Deposit models
class DepositStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class DepositBase(BaseModel):
    user_id: PyObjectId
    amount: float
    reference: str
    status: DepositStatus = DepositStatus.PENDING

class DepositCreate(DepositBase):
    pass

class DepositUpdate(BaseModel):
    status: DepositStatus

class Deposit(DepositBase, MongoBaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Transaction models
class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    GAME = "game"
    WITHDRAWAL = "withdrawal"

class GameResult(str, Enum):
    WIN = "win"
    LOSE = "lose"

class TransactionBase(BaseModel):
    # user_id: PyObjectId
    user_id: Optional[str] = None
    type: TransactionType
    amount: float
    game_id: Optional[PyObjectId] = None
    game_name: Optional[str] = None
    result: Optional[GameResult] = None
    payout: Optional[float] = None
    reference: Optional[str] = None

class TransactionCreate(TransactionBase):
    timestamp: Optional[datetime] = None

class Transaction(TransactionBase, MongoBaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BankAccount(BaseModel):
    account_number: str = Field(..., min_length=10, max_length=20)
    account_name: str = Field(..., min_length=2, max_length=100)
    bank_name: str = Field(..., min_length=2, max_length=100)
    bank_code: Optional[str] = None


class WithdrawalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class WithdrawalBase(BaseModel):
    user_id: PyObjectId
    amount: float = Field(..., gt=0)
    bank_account: BankAccount
    status: WithdrawalStatus = WithdrawalStatus.PENDING
    reference: Optional[str] = None

class WithdrawalCreate(BaseModel):
    amount: float = Field(..., gt=0)
    bank_account: BankAccount
    reference: Optional[str] = None

class WithdrawalUpdate(BaseModel):
    status: WithdrawalStatus
    admin_notes: Optional[str] = None

class Withdrawal(WithdrawalBase, MongoBaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('user_id', mode='before')
    def convert_objectid_to_str(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

# Token model
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: str
    role: UserRole
