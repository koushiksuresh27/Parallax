import uuid
from datetime import datetime

from pydantic import BaseModel


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    file_type: str
    status: str
    row_count: int | None = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class SourceDetailResponse(SourceResponse):
    file_path: str
    file_hash: str | None = None

