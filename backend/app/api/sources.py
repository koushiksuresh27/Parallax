import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.sources import DataSource
from app.schemas.sources import SourceResponse, SourceDetailResponse
from app.ingestion.file_service import validate_and_save_file
from app.ingestion.background_tasks import process_source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", status_code=201, response_model=SourceResponse)
async def upload_source(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a data source file. Starts background processing."""
    try:
        source = await validate_and_save_file(file, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Fire-and-forget background processing
    asyncio.create_task(process_source(source.id))

    return source


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List all uploaded data sources."""
    result = await session.execute(
        select(DataSource)
        .order_by(DataSource.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{source_id}", response_model=SourceDetailResponse)
async def get_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get details of a specific data source."""
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/{source_id}/retry", response_model=SourceResponse)
async def retry_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Retry processing a failed source."""
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status != "failed":
        raise HTTPException(status_code=400, detail=f"Source status is '{source.status}', not 'failed'")

    source.status = "pending"
    await session.commit()

    asyncio.create_task(process_source(source.id))

    return source

