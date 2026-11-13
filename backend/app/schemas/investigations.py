import uuid
from datetime import datetime

from pydantic import BaseModel


class InvestigationCreate(BaseModel):
    question: str


class InvestigationResponse(BaseModel):
    id: uuid.UUID
    question: str
    status: str
    current_node: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    source_type: str
    record_id: str | None = None
    content: str
    relevance_score: float | None = None

    model_config = {"from_attributes": True}


class FindingResponse(BaseModel):
    id: uuid.UUID
    finding_type: str
    content: str
    confidence: str | None = None
    evidence_ids: list[uuid.UUID] | None = None

    model_config = {"from_attributes": True}


class InvestigationDetailResponse(InvestigationResponse):
    evidence: list[EvidenceResponse] = []
    findings: list[FindingResponse] = []

