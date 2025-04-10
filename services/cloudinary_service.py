import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
from core.config import settings

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)


async def upload_image(file: UploadFile) -> str:
    """
    Upload an image to Cloudinary and return the URL
    """
    # Read file content
    contents = await file.read()

    # Upload to Cloudinary
    result = cloudinary.uploader.upload(contents)

    # Return the URL
    return result["secure_url"]
