from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


IncidentSeverity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "investigating", "resolved", "closed"]


class IncidentCaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    system_name: str | None = Field(default=None, max_length=200)
    severity: IncidentSeverity = "medium"
    status: IncidentStatus = "open"
    symptom: str = Field(min_length=1)
    cause: str | None = None
    investigation_process: str | None = None
    solution: str | None = None
    review_conclusion: str | None = None
    occurred_at: datetime | None = None
    resolved_at: datetime | None = None

    @field_validator("title", "symptom")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field cannot be blank")
        return normalized

    @field_validator(
        "system_name",
        "cause",
        "investigation_process",
        "solution",
        "review_conclusion",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class IncidentCaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    system_name: str | None = Field(default=None, max_length=200)
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    symptom: str | None = Field(default=None, min_length=1)
    cause: str | None = None
    investigation_process: str | None = None
    solution: str | None = None
    review_conclusion: str | None = None
    occurred_at: datetime | None = None
    resolved_at: datetime | None = None

    @field_validator("title", "symptom")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("field cannot be blank")
        return normalized

    @field_validator(
        "system_name",
        "cause",
        "investigation_process",
        "solution",
        "review_conclusion",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class IncidentCaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    system_name: str | None
    severity: IncidentSeverity
    status: IncidentStatus
    occurred_at: datetime | None
    resolved_at: datetime | None
    wiki_page_id: int | None
    created_at: datetime
    updated_at: datetime


class IncidentCaseResponse(IncidentCaseListItem):
    symptom: str
    cause: str | None
    investigation_process: str | None
    solution: str | None
    review_conclusion: str | None
    created_by_user_id: int | None
    updated_by_user_id: int | None


class IncidentRelationshipBuildResponse(BaseModel):
    incident_id: int
    wiki_page_id: int
    created_page_ids: list[int]
    updated_page_ids: list[int]
    relationship_ids: list[int]
    similar_incident_ids: list[int]
