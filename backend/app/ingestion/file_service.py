import hashlib
import os
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sources import DataSource

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
ALLOWED_TYPES = {"csv", "xlsx", "pdf", "docx", "txt", "json"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def get_file_extension(filename: str) -> str:
    """Extract lowercase file extension without the dot."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def validate_and_save_file(
    file: UploadFile,
    session: AsyncSession,
) -> DataSource:
    """
    Validate file type and size, check for duplicates, save to disk,
    and create a DataSource record with status='pending'.
    Returns the DataSource. Raises ValueError on validation failure.
    """
    # Validate file type
    ext = get_file_extension(file.filename or "")
    if ext not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: .{ext}. Allowed: {', '.join(ALLOWED_TYPES)}")

    # Read file content
    content = await file.read()

    # Validate size
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(content)} bytes. Max: {MAX_FILE_SIZE} bytes")

    # Compute hash for duplicate detection
    file_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicates
    existing = await session.execute(
        select(DataSource).where(DataSource.file_hash == file_hash)
    )
    if existing.scalar_one_or_none():
        raise FileExistsError(f"Duplicate file detected (hash: {file_hash[:16]}...)")

    # Save file to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4()
    saved_filename = f"{file_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # Create DataSource record
    source = DataSource(
        id=file_id,
        name=file.filename or saved_filename,
        file_type=ext,
        file_path=file_path,
        file_hash=file_hash,
        status="pending",
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    return source

