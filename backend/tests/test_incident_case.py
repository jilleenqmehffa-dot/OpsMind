from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers all mapped tables for the test database
from app.db.base import Base
from app.models.incident_case import IncidentCase
from app.schemas.incident_case import (
    IncidentCaseCreate,
    IncidentCaseResponse,
    IncidentCaseUpdate,
)


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["incident_cases"]])
    return Session(engine)


def test_incident_case_create_normalizes_text_and_defaults() -> None:
    payload = IncidentCaseCreate(
        title="  PostgreSQL 主从延迟  ",
        system_name="  database  ",
        symptom="  只读节点延迟持续升高  ",
        cause="   ",
    )

    assert payload.title == "PostgreSQL 主从延迟"
    assert payload.system_name == "database"
    assert payload.symptom == "只读节点延迟持续升高"
    assert payload.cause is None
    assert payload.severity == "medium"
    assert payload.status == "open"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("symptom", "   "),
        ("severity", "urgent"),
        ("status", "unknown"),
    ],
)
def test_incident_case_create_rejects_invalid_fields(field: str, value: str) -> None:
    data = {"title": "数据库故障", "symptom": "连接失败", field: value}

    with pytest.raises(ValidationError):
        IncidentCaseCreate(**data)


def test_incident_case_update_preserves_explicit_null_for_optional_fields() -> None:
    payload = IncidentCaseUpdate(cause=None, solution="  重启连接池  ")

    assert payload.model_dump(exclude_unset=True) == {
        "cause": None,
        "solution": "重启连接池",
    }


def test_incident_case_model_persists_and_serializes() -> None:
    with make_session() as db:
        incident = IncidentCase(
            title="Redis 连接耗尽",
            system_name="cache",
            severity="high",
            status="investigating",
            symptom="应用无法获取 Redis 连接。",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        response = IncidentCaseResponse.model_validate(incident)

        assert response.id == incident.id
        assert response.severity == "high"
        assert response.status == "investigating"
        assert response.wiki_page_id is None
        assert response.created_at is not None


def test_incident_case_database_rejects_invalid_status() -> None:
    with make_session() as db:
        db.add(
            IncidentCase(
                title="无效状态案例",
                severity="medium",
                status="invalid",
                symptom="用于验证数据库约束。",
            )
        )

        with pytest.raises(IntegrityError, match="ck_incident_cases_status"):
            db.commit()
