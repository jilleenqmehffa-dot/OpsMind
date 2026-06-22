from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.models  # noqa: F401 - registers mapped tables
from app.api.routes import incident_cases as incident_route
from app.db.base import Base
from app.models.incident_case import IncidentCase
from app.models.user import User
from app.models.wiki_page import WikiPage
from app.models.wiki_page_tag import WikiPageTag
from app.models.wiki_version import WikiVersion
from app.schemas.wiki import WikiPageCreate
from app.services.incident_wiki import render_incident_markdown


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            WikiPage.__table__,
            WikiPageTag.__table__,
            WikiVersion.__table__,
            IncidentCase.__table__,
        ],
    )
    return Session(engine)


def make_user() -> User:
    return User(
        id=11,
        username="publisher",
        password_hash="unused",
        is_active=True,
        is_superuser=False,
    )


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/incidents/1/publish-to-wiki",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def add_incident(db: Session) -> IncidentCase:
    incident = IncidentCase(
        title="PostgreSQL 主从延迟",
        system_name="database",
        severity="high",
        status="resolved",
        symptom="只读节点延迟持续升高。",
        cause="归档任务产生大量写入。",
        investigation_process="检查复制槽与 WAL 生成速率。",
        solution="暂停归档任务并扩容只读节点。",
        review_conclusion="为归档任务增加流量限制。",
        occurred_at=datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def test_publish_incident_creates_then_updates_one_wiki_page(monkeypatch) -> None:
    audit_details: list[dict[str, object]] = []

    def fake_record_audit_log(db, *, detail, **kwargs):
        audit_details.append(detail)

    monkeypatch.setattr(incident_route, "record_audit_log", fake_record_audit_log)

    with make_session() as db:
        incident = add_incident(db)
        first = incident_route.publish_incident(incident.id, make_request(), db, make_user())

        assert first.page_type == "incident"
        assert first.status == "published"
        assert first.slug == f"incident-{incident.id}"
        assert "## 故障现象" in first.content
        assert "归档任务产生大量写入" in first.content
        assert db.get(IncidentCase, incident.id).wiki_page_id == first.id

        incident.solution = "调整归档窗口并限制写入速率。"
        db.commit()
        second = incident_route.publish_incident(incident.id, make_request(), db, make_user())

        assert second.id == first.id
        assert "调整归档窗口" in second.content
        versions = list(
            db.scalars(
                select(WikiVersion)
                .where(WikiVersion.page_id == first.id)
                .order_by(WikiVersion.version_number)
            ).all()
        )
        assert [version.version_number for version in versions] == [1, 2]
        assert "暂停归档任务" in versions[0].content
        assert "调整归档窗口" in versions[1].content

    assert [detail["publish_action"] for detail in audit_details] == ["created", "updated"]
    assert {detail["wiki_page_id"] for detail in audit_details} == {first.id}


def test_publish_incident_rejects_generated_slug_conflict(monkeypatch) -> None:
    monkeypatch.setattr(incident_route, "record_audit_log", lambda *args, **kwargs: None)

    with make_session() as db:
        incident = add_incident(db)
        db.add(
            WikiPage(
                title="人工页面",
                slug=f"incident-{incident.id}",
                content="不应被故障案例覆盖。",
                page_type="concept",
                status="published",
            )
        )
        db.commit()

        with pytest.raises(HTTPException, match="slug is already in use") as captured:
            incident_route.publish_incident(incident.id, make_request(), db, make_user())

        assert captured.value.status_code == 409
        assert db.get(IncidentCase, incident.id).wiki_page_id is None


def test_incident_template_marks_missing_optional_content() -> None:
    incident = IncidentCase(
        id=3,
        title="未知原因故障",
        severity="medium",
        status="investigating",
        symptom="服务不可用。",
    )

    content = render_incident_markdown(incident)

    assert "> 来源：故障案例 #3" in content
    assert content.count("未记录") >= 5


def test_wiki_page_type_schema_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        WikiPageCreate(
            title="无效页面",
            slug="invalid-page",
            content="正文",
            page_type="unknown",
        )
