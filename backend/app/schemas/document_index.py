from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentIndexJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    attachment_id: int
    status: str
    chunk_count: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
