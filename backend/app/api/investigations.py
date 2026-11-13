import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.investigations import Investigation, InvestigationEvidence, InvestigationFinding
from app.schemas.investigations import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationDetailResponse,
    EvidenceResponse,
)
from app.investigation.runner import run_investigation

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.post("", status_code=202, response_model=InvestigationResponse)
async def create_investigation(
    body: InvestigationCreate,
    session: AsyncSession = Depends(get_session),
):
    """Start a new investigation. Returns immediately with investigation ID."""
    investigation = Investigation(
        question=body.question,
        status="pending",
    )
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)

    # Fire-and-forget the workflow
    asyncio.create_task(run_investigation(investigation.id, body.question))

    return investigation


@router.get("", response_model=list[InvestigationResponse])
async def list_investigations(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List all investigations, most recent first."""
    result = await session.execute(
        select(Investigation)
        .order_by(Investigation.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{investigation_id}", response_model=InvestigationDetailResponse)
async def get_investigation(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get investigation details including evidence and findings."""
    result = await session.execute(
        select(Investigation)
        .where(Investigation.id == investigation_id)
        .options(
            selectinload(Investigation.evidence),
            selectinload(Investigation.findings),
        )
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation


@router.get("/{investigation_id}/evidence", response_model=list[EvidenceResponse])
async def get_investigation_evidence(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get all evidence records for an investigation."""
    investigation = await session.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    result = await session.execute(
        select(InvestigationEvidence)
        .where(InvestigationEvidence.investigation_id == investigation_id)
    )
    return result.scalars().all()

