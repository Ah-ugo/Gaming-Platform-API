import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Gaming Platform API"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = ["*"]

    # MongoDB
    MONGODB_URL: str = os.getenv("MONGO_URL")
    MONGODB_DB_NAME: str = "gaming_platform"

    # Cloudinary (will accept both CLOUDINARY_CLOUD_NAME and CLOUD_NAME)
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUD_NAME")
    CLOUDINARY_API_KEY: str = os.getenv("API_KEY")
    CLOUDINARY_API_SECRET: str = os.getenv("API_SECRET")

    # Google Auth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_API_URL: str = ""

    # Email
    GMAIL_ADDRESS: str = ""
    GMAIL_PASS: str = ""

    @field_validator('CLOUDINARY_CLOUD_NAME', mode='before')
    def get_cloud_name(cls, v):
        return v or os.getenv("CLOUD_NAME", "")

    @field_validator('CLOUDINARY_API_KEY', mode='before')
    def get_api_key(cls, v):
        return v or os.getenv("API_KEY", "")

    @field_validator('CLOUDINARY_API_SECRET', mode='before')
    def get_api_secret(cls, v):
        return v or os.getenv("API_SECRET", "")

    @field_validator('MONGODB_URL', mode='before')
    def get_mongo_url(cls, v):
        return v or os.getenv("MONGO_URL", "mongodb://localhost:27017")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # This will ignore extra fields in .env


settings = Settings()