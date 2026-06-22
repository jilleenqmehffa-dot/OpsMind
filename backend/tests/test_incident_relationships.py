from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.models  # noqa: F401 - registers mapped tables
from app.api.routes import incident_cases as incident_route
from app.db.base import Base
from app.models.incident_case import IncidentCase
from app.models.user import User
from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.models.wiki_page_tag import WikiPageTag
from app.models.wiki_version import WikiVersion


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            WikiPage.__table__,
            WikiPageTag.__table__,
            WikiVersion.__table__,
            WikiPageRelationship.__table__,
            IncidentCase.__table__,
        ],
    )
    return Session(engine)


def make_user() -> User:
    return User(id=21, username="builder", password_hash="unused", is_active=True, is_superuser=False)


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/incidents/1/build-wiki-relationships",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def add_incident(db: Session, *, title: str, symptom: str, cause: str, solution: str) -> IncidentCase:
    incident = IncidentCase(
        title=title,
        system_name="PostgreSQL",
        severity="high",
        status="resolved",
        symptom=symptom,
        cause=cause,
        investigation_process="检查复制槽和 WAL 生成速率。",
        solution=solution,
        occurred_at=datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def test_build_relationships_is_repeatable_and_updates_generated_pages(monkeypatch) -> None:
    audit_details: list[dict[str, object]] = []
    monkeypatch.setattr(
        incident_route,
        "record_audit_log",
        lambda db, *, detail, **kwargs: audit_details.append(detail),
    )

    with make_session() as db:
        first = add_incident(
            db,
            title="PostgreSQL 主从延迟",
            symptom="PostgreSQL 只读节点复制延迟持续升高。",
            cause="归档任务产生大量写入。",
            solution="暂停归档任务并扩容只读节点。",
        )
        second = add_incident(
            db,
            title="PostgreSQL 复制延迟",
            symptom="PostgreSQL 只读节点复制延迟突然升高。",
            cause="批处理任务写入过多。",
            solution="限制批处理写入速率。",
        )
        incident_route.publish_incident(first.id, make_request(), db, make_user())
        incident_route.publish_incident(second.id, make_request(), db, make_user())

        built = incident_route.build_incident_wiki_relationships(first.id, make_request(), db, make_user())

        assert len(built.created_page_ids) == 3
        assert built.updated_page_ids == []
        assert built.similar_incident_ids == [second.id]
        relationships = list(
            db.scalars(
                select(WikiPageRelationship).where(WikiPageRelationship.id.in_(built.relationship_ids))
            ).all()
        )
        assert {item.relation_type for item in relationships} == {
            "belongs_to",
            "caused_by",
            "resolved_by",
            "similar_to",
        }
        assert all(item.source_type == "incident_case" for item in relationships)

        repeated = incident_route.build_incident_wiki_relationships(first.id, make_request(), db, make_user())
        assert repeated.created_page_ids == []
        assert repeated.updated_page_ids == []
        assert set(repeated.relationship_ids) == set(built.relationship_ids)

        first.solution = "调整归档窗口并限制写入速率。"
        db.commit()
        changed = incident_route.build_incident_wiki_relationships(first.id, make_request(), db, make_user())
        assert len(changed.updated_page_ids) == 1
        solution_page = db.get(WikiPage, changed.updated_page_ids[0])
        assert solution_page.page_type == "process"
        assert "调整归档窗口" in solution_page.content
        versions = list(
            db.scalars(select(WikiVersion).where(WikiVersion.page_id == solution_page.id)).all()
        )
        assert len(versions) == 2

    assert len(audit_details) == 5
    assert audit_details[-1]["updated_page_count"] == 1


def test_build_relationships_requires_published_incident(monkeypatch) -> None:
    monkeypatch.setattr(incident_route, "record_audit_log", lambda *args, **kwargs: None)

    with make_session() as db:
        incident = add_incident(
            db,
            title="未发布故障",
            symptom="服务异常。",
            cause="配置错误。",
            solution="修复配置。",
        )

        with pytest.raises(HTTPException, match="Publish the incident") as captured:
            incident_route.build_incident_wiki_relationships(incident.id, make_request(), db, make_user())

        assert captured.value.status_code == 409
