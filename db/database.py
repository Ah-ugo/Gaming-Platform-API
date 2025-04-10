import motor.motor_asyncio
from core.config import settings

client = None
db = None

async def connect_to_mongo():
    global client, db
    client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    print(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("Closed MongoDB connection")

def get_database():
    return db
