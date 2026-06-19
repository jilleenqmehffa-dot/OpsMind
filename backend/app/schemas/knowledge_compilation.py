from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeCompilationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int | None
    attachment_id: int
    status: str
    knowledge_unit_count: int
    created_page_count: int
    updated_page_count: int
    relationship_count: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    source_attachment_id: int
    source_page_id: int | None
    title: str
    unit_type: str
    summary: str
    content: str
    source_location: str
    confidence: float
    merge_hint_page_id: int | None
    merge_hint_title: str | None
    apply_status: str
    review_note: str | None
    created_page_id: int | None
    created_at: datetime
    updated_at: datetime


class KnowledgeUnitApplyRequest(BaseModel):
    action: str = Field(pattern="^(apply|skip|reject)$")
    target_page_id: int | None = None
    review_note: str | None = None
