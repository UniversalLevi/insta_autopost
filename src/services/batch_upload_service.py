"""Service for handling batch content uploads and scheduling."""

import zipfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from fastapi import UploadFile

from ..utils.logger import get_logger
from .batch_campaign_store import (
    create_campaign,
    add_scheduled_post_to_campaign,
    add_error_to_campaign,
    mark_campaign_failed,
    get_campaign,
)
from .scheduled_posts_store import add_scheduled

logger = get_logger(__name__)

# Supported file formats
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
SUPPORTED_FORMATS = SUPPORTED_IMAGE_FORMATS | SUPPORTED_VIDEO_FORMATS

# Limits
MAX_FILES_PER_CAMPAIGN = 31
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def validate_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate a file for batch upload.
    Returns (is_valid, error_message)
    """
    if not file_path.exists():
        return False, f"File not found: {file_path.name}"
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f"File too large: {file_path.name} ({file_size / 1024 / 1024:.2f} MB, max {MAX_FILE_SIZE_MB} MB)"
    
    if file_size == 0:
        return False, f"File is empty: {file_path.name}"
    
    # Check extension
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        return False, f"Unsupported format: {file_path.name} (supported: {', '.join(SUPPORTED_FORMATS)})"
    
    return True, None


def extract_zip(zip_path: Path, extract_to: Path) -> List[Path]:
    """
    Extract ZIP file and return list of extracted file paths.
    Skips unsupported files and validates each extracted file.
    Flattens nested directories while preserving unique filenames.
    """
    extracted_files = []
    file_counter = {}  # Track filename collisions
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get list of files in ZIP
            file_list = zip_ref.namelist()
            
            for file_name in file_list:
                # Skip directories
                if file_name.endswith('/'):
                    continue
                
                # Skip hidden files and __MACOSX
                if file_name.startswith('.') or '__MACOSX' in file_name:
                    continue
                
                # Get base filename
                base_name = Path(file_name).name
                if not base_name:
                    continue
                
                # Check file extension (case-insensitive)
                ext = Path(base_name).suffix.lower()
                if ext not in SUPPORTED_FORMATS:
                    logger.debug("Skipping unsupported file from ZIP", file_name=file_name, ext=ext)
                    continue
                
                # Extract file
                try:
                    # Extract to temporary location first
                    zip_ref.extract(file_name, extract_to)
                    extracted_path = extract_to / file_name
                    
                    # Handle nested directories - flatten to extract_to root
                    if extracted_path != extract_to / base_name:
                        # Determine final filename (handle collisions)
                        final_name = base_name
                        final_path = extract_to / final_name
                        
                        # If file already exists, add counter
                        if final_path.exists():
                            counter = 1
                            name_part = Path(base_name).stem
                            ext_part = Path(base_name).suffix
                            while final_path.exists():
                                final_name = f"{name_part}_{counter}{ext_part}"
                                final_path = extract_to / final_name
                                counter += 1
                        
                        # Move file to root of extract_to
                        if extracted_path.exists() and extracted_path.is_file():
                            # Create parent directory if needed
                            final_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Move the file
                            shutil.move(str(extracted_path), str(final_path))
                            extracted_path = final_path
                            
                            # Clean up empty parent directories
                            try:
                                # Start from the original extracted path's parent
                                cleanup_path = Path(file_name).parent
                                if cleanup_path and cleanup_path != Path('.'):
                                    # Try to clean up nested directories
                                    for part in reversed(cleanup_path.parts):
                                        if part:
                                            dir_to_remove = extract_to / part
                                            if dir_to_remove.exists() and dir_to_remove.is_dir():
                                                try:
                                                    if not any(dir_to_remove.iterdir()):
                                                        dir_to_remove.rmdir()
                                                except OSError:
                                                    pass
                            except Exception as cleanup_err:
                                logger.debug("Failed to clean up directories", error=str(cleanup_err))
                    else:
                        # File is already at root, just ensure it exists
                        final_path = extracted_path
                    
                    # Validate extracted file
                    if extracted_path.exists() and extracted_path.is_file():
                        is_valid, error = validate_file(extracted_path)
                        if is_valid:
                            extracted_files.append(extracted_path)
                        else:
                            logger.warning("Skipping invalid file from ZIP", file_name=file_name, error=error)
                            if extracted_path.exists():
                                extracted_path.unlink()
                    else:
                        logger.warning("Extracted path is not a file", file_name=file_name, path=str(extracted_path))
                        
                except Exception as e:
                    logger.warning("Failed to extract file from ZIP", file_name=file_name, error=str(e))
                    continue
        
        logger.info("ZIP extraction complete", zip_path=str(zip_path), extracted_count=len(extracted_files))
        return extracted_files
    
    except zipfile.BadZipFile:
        raise ValueError(f"Invalid ZIP file: {zip_path.name}")
    except Exception as e:
        raise ValueError(f"Failed to extract ZIP: {str(e)}")


def infer_media_type(file_path: Path) -> str:
    """Infer media type from file extension."""
    ext = file_path.suffix.lower()
    if ext in SUPPORTED_VIDEO_FORMATS:
        return "video"
    return "image"


async def save_uploaded_file(file: UploadFile, save_path: Path) -> Path:
    """Save an uploaded file to disk."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return save_path


def process_batch_upload(
    account_id: str,
    files: List[Path],
    start_date: datetime,
    end_date: Optional[datetime] = None,
    caption: str = "",
    hashtags: Optional[List[str]] = None,
    base_url: str = "",
) -> Dict[str, Any]:
    """
    Process batch upload: create campaign and schedule posts.
    
    Args:
        account_id: Target account ID
        files: List of file paths (already validated)
        start_date: Start date for first post
        end_date: Optional end date. If provided, files are distributed across the date range.
        caption: Caption for all posts
        hashtags: Hashtags for all posts
        base_url: Base URL for serving uploaded files (e.g., "http://localhost:8000")
    
    Returns:
        Dict with campaign_id, scheduled_count, errors
    """
    # Validate file count
    if len(files) > MAX_FILES_PER_CAMPAIGN:
        raise ValueError(f"Too many files: {len(files)} (max {MAX_FILES_PER_CAMPAIGN})")
    
    if len(files) == 0:
        raise ValueError("No valid files provided")
    
    # Calculate date range and distribution
    if end_date:
        # Validate end date is after start date
        if end_date <= start_date:
            raise ValueError("End date must be after start date")
        
        # Calculate total days in range (inclusive)
        total_days = (end_date - start_date).days + 1
        
        # Calculate how to distribute files
        if len(files) <= total_days:
            # Fewer or equal files than days: one file per day, evenly distributed
            if len(files) == 1:
                day_offsets = [0]
            else:
                day_offsets = [int(i * (total_days - 1) / (len(files) - 1)) for i in range(len(files))]
        else:
            # More files than days: distribute evenly across days
            files_per_day = len(files) / total_days
            day_offsets = []
            for i in range(len(files)):
                day_offsets.append(int(i / files_per_day))
    else:
        # No end date: schedule one per day from start_date
        total_days = len(files)  # Set total_days for later use
        day_offsets = list(range(len(files)))
    
    # Create campaign
    campaign_id = create_campaign(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        caption=caption,
        hashtags=hashtags or [],
        file_count=len(files),
    )
    
    scheduled_count = 0
    errors = []
    
    # Schedule each file
    for file_index, file_path in enumerate(files):
        try:
            # Calculate scheduled time using pre-calculated day offsets
            day_offset = day_offsets[file_index]
            scheduled_time = start_date + timedelta(days=day_offset)
            
            # If multiple files on same day, distribute across hours
            if end_date and len(files) > total_days:
                # Count how many files are scheduled for this day
                files_on_this_day = day_offsets.count(day_offset)
                if files_on_this_day > 1:
                    # Get index of this file among files on this day
                    file_index_on_day = [i for i, d in enumerate(day_offsets) if d == day_offset].index(file_index)
                    # Distribute across 24 hours (avoid posting at same time)
                    hours_spread = 24 / files_on_this_day
                    hour_offset = int(file_index_on_day * hours_spread)
                    scheduled_time = scheduled_time.replace(
                        hour=(start_date.hour + hour_offset) % 24,
                        minute=start_date.minute
                    )
            
            # Infer media type
            media_type = infer_media_type(file_path)
            
            # Generate URL for the file
            # Files should be in /uploads/batch/{campaign_id}/
            # Convert Windows path separators to forward slashes
            relative_path = file_path.relative_to(Path("uploads"))
            # Ensure URL includes /uploads/ prefix for file serving route
            file_url = f"{base_url.rstrip('/')}/uploads/{str(relative_path).replace(chr(92), '/')}?t={int(datetime.utcnow().timestamp())}"
            
            # Add scheduled post using existing scheduler
            post_id = add_scheduled(
                account_id=account_id,
                media_type=media_type,
                urls=[file_url],
                caption=caption,
                scheduled_time=scheduled_time,
                hashtags=hashtags,
            )
            
            # Link post to campaign
            add_scheduled_post_to_campaign(campaign_id, post_id)
            scheduled_count += 1
            
            logger.info(
                "Batch post scheduled",
                campaign_id=campaign_id,
                post_id=post_id,
                day_offset=day_offset,
                scheduled_time=scheduled_time.isoformat(),
                file_name=file_path.name,
            )
        
        except Exception as e:
            error_msg = f"Failed to schedule file {file_path.name}: {str(e)}"
            errors.append(error_msg)
            add_error_to_campaign(campaign_id, error_msg)
            logger.error("Batch scheduling error", campaign_id=campaign_id, file_name=file_path.name, error=str(e))
    
    # Check if campaign should be marked as failed
    error_threshold = len(files) * 0.2  # 20% error threshold
    if len(errors) > error_threshold:
        mark_campaign_failed(campaign_id, f"Too many errors: {len(errors)}/{len(files)}")
    
    return {
        "campaign_id": campaign_id,
        "scheduled_count": scheduled_count,
        "total_files": len(files),
        "errors": errors,
        "status": "failed" if len(errors) > error_threshold else "active",
    }
