"""Cloudinary helper for uploading media files"""

import os
from typing import Optional
from pathlib import Path

# Try to import cloudinary
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

def init_cloudinary():
    """Initialize Cloudinary with credentials from environment variables"""
    if not CLOUDINARY_AVAILABLE:
        return False
    
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    
    if not cloud_name or not api_key or not api_secret:
        return False
    
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True  # Always use HTTPS
    )
    
    return True

def upload_to_cloudinary(file_path: Path, public_id: Optional[str] = None) -> Optional[str]:
    """
    Upload a file to Cloudinary and return the public URL
    
    Args:
        file_path: Path to the file to upload
        public_id: Optional public ID for the file (if None, uses filename)
        
    Returns:
        Public HTTPS URL of the uploaded file, or None if upload fails
    """
    if not CLOUDINARY_AVAILABLE:
        return None
    
    if not init_cloudinary():
        return None
    
    try:
        # Determine resource type from file extension
        ext = file_path.suffix.lower()
        resource_type = "auto"  # Cloudinary auto-detects
        
        if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".ico"]:
            resource_type = "image"
        elif ext in [".mp4", ".mov", ".avi", ".webm", ".flv", ".mkv"]:
            resource_type = "video"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            str(file_path),
            resource_type=resource_type,
            public_id=public_id,
            folder="instaforge",  # Organize files in a folder
            overwrite=False,  # Don't overwrite existing files
            invalidate=True,  # Invalidate CDN cache
        )
        
        # Return the secure HTTPS URL
        url = result.get("secure_url") or result.get("url")
        return url
        
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return None

def is_cloudinary_configured() -> bool:
    """Check if Cloudinary is configured"""
    if not CLOUDINARY_AVAILABLE:
        return False
    
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    
    return bool(cloud_name and api_key and api_secret)
