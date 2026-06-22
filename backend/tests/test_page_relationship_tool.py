import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers mapped tables
from app.db.base import Base
from app.models.knowledge_compilation_job import KnowledgeCompilationJob
from app.models.knowledge_unit import KnowledgeUnit
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tool_invocation import ToolInvocation
from app.models.user import User
from app.models.user_role import UserRole
from app.models.wiki_attachment import WikiAttachment
from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.executor import execute_tool
from app.tools.page_relationship import PageRelationshipOutput
from app.tools.registry import build_default_tool_registry


TABLES = [
    User.__table__,
    Role.__table__,
    Permission.__table__,
    UserRole.__table__,
    RolePermission.__table__,
    WikiPage.__table__,
    WikiAttachment.__table__,
    KnowledgeCompilationJob.__table__,
    KnowledgeUnit.__table__,
    WikiPageRelationship.__table__,
    ToolInvocation.__table__,
]


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def seed_applied_unit(
    db: Session,
    *,
    superuser: bool = True,
) -> tuple[User, KnowledgeUnit, WikiPage, WikiPage, WikiPage]:
    actor = User(
        username="relationship-actor",
        password_hash="unused",
        is_active=True,
        is_superuser=superuser,
    )
    source = WikiPage(
        title="Redis incident",
        slug="redis-incident",
        content="Incident",
        page_type="incident",
        status="published",
        author=actor,
    )
    generated = WikiPage(
        title="Redis recovery",
        slug="redis-recovery",
        content="Recovery",
        page_type="process",
        status="draft",
        author=actor,
    )
    target = WikiPage(
        title="Redis cluster",
        slug="redis-cluster",
        content="Cluster",
        page_type="system",
        status="published",
        author=actor,
    )
    db.add_all([actor, source, generated, target])
    db.flush()
    attachment = WikiAttachment(
        page_id=source.id,
        filename="incident.md",
        content_type="text/markdown",
        size_bytes=100,
        storage_path="backend/storage/uploads/incident.md",
        uploaded_by_user_id=actor.id,
    )
    db.add(attachment)
    db.flush()
    job = KnowledgeCompilationJob(
        page_id=source.id,
        attachment_id=attachment.id,
        status="ready",
        knowledge_unit_count=1,
        created_page_count=1,
    )
    db.add(job)
    db.flush()
    unit = KnowledgeUnit(
        job_id=job.id,
        source_attachment_id=attachment.id,
        source_page_id=source.id,
        title="Redis recovery",
        unit_type="process",
        summary="Recovery summary",
        content="Recovery content",
        source_location="section:1",
        confidence=0.9,
        apply_status="applied",
        created_page_id=generated.id,
    )
    db.add(unit)
    db.commit()
    for item in (actor, unit, source, generated, target):
        db.refresh(item)
    return actor, unit, source, generated, target


def test_creates_provenance_linked_relationship_and_audit_summary() -> None:
    with make_session() as db:
        actor, unit, _, generated, target = seed_applied_unit(db)
        result = execute_tool(
            build_default_tool_registry(),
            "page_relationship",
            {
                "knowledge_unit_id": unit.id,
                "source_page_id": generated.id,
                "target_page_id": target.id,
                "relation_type": "depends_on",
                "description": "Recovery depends on the Redis cluster.",
            },
            ToolContext(db=db, actor_user_id=actor.id),
        )

        assert isinstance(result, PageRelationshipOutput)
        relationship = db.get(WikiPageRelationship, result.relationship_id)
        assert relationship.source_type == "knowledge_compilation"
        assert relationship.source_job_id == unit.job_id
        assert relationship.created_by_user_id == actor.id
        db.refresh(unit.job)
        assert unit.job.relationship_count == 1

        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "success"
        assert invocation.result_summary == result.model_dump()


def test_symmetric_relationship_normalizes_direction_and_rejects_reverse_duplicate() -> None:
    with make_session() as db:
        actor, unit, source, generated, _ = seed_applied_unit(db)
        first = execute_tool(
            build_default_tool_registry(),
            "page_relationship",
            {
                "knowledge_unit_id": unit.id,
                "source_page_id": generated.id,
                "target_page_id": source.id,
                "relation_type": "similar_to",
            },
            ToolContext(db=db, actor_user_id=actor.id),
        )
        assert (first.source_page_id, first.target_page_id) == tuple(sorted((source.id, generated.id)))

        with pytest.raises(ToolInvocationError) as duplicate:
            execute_tool(
                build_default_tool_registry(),
                "page_relationship",
                {
                    "knowledge_unit_id": unit.id,
                    "source_page_id": source.id,
                    "target_page_id": generated.id,
                    "relation_type": "similar_to",
                },
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert duplicate.value.code == "relationship_conflict"
        assert len(db.scalars(select(WikiPageRelationship)).all()) == 1


def test_relationship_must_touch_a_page_linked_to_the_unit() -> None:
    with make_session() as db:
        actor, unit, _, _, target = seed_applied_unit(db)
        unrelated = WikiPage(
            title="Unrelated",
            slug="unrelated",
            content="Unrelated",
            page_type="concept",
            status="draft",
            author_user_id=actor.id,
        )
        db.add(unrelated)
        db.commit()

        with pytest.raises(ToolInvocationError) as mismatch:
            execute_tool(
                build_default_tool_registry(),
                "page_relationship",
                {
                    "knowledge_unit_id": unit.id,
                    "source_page_id": target.id,
                    "target_page_id": unrelated.id,
                    "relation_type": "related_to",
                },
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert mismatch.value.code == "knowledge_unit_page_mismatch"


def test_requires_applied_unit_and_rejects_self_relationship() -> None:
    with make_session() as db:
        actor, unit, source, generated, _ = seed_applied_unit(db)
        unit.apply_status = "pending"
        db.commit()
        with pytest.raises(ToolInvocationError) as not_applied:
            execute_tool(
                build_default_tool_registry(),
                "page_relationship",
                {
                    "knowledge_unit_id": unit.id,
                    "source_page_id": source.id,
                    "target_page_id": generated.id,
                    "relation_type": "references",
                },
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert not_applied.value.code == "knowledge_unit_not_applied"

        unit.apply_status = "applied"
        db.commit()
        with pytest.raises(ToolInvocationError) as self_relation:
            execute_tool(
                build_default_tool_registry(),
                "page_relationship",
                {
                    "knowledge_unit_id": unit.id,
                    "source_page_id": source.id,
                    "target_page_id": source.id,
                    "relation_type": "references",
                },
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert self_relation.value.code == "self_relationship"


def test_requires_wiki_update_permission_and_valid_relation_type() -> None:
    with make_session() as db:
        actor, unit, source, generated, _ = seed_applied_unit(db, superuser=False)
        with pytest.raises(ToolInvocationError) as denied:
            execute_tool(
                build_default_tool_registry(),
                "page_relationship",
                {
                    "knowledge_unit_id": unit.id,
                    "source_page_id": source.id,
                    "target_page_id": generated.id,
                    "relation_type": "references",
                },
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert denied.value.code == "permission_denied"

        actor.is_superuser = True
        db.commit()
        with pytest.raises(ToolInvocationError) as invalid:
            execute_tool(
                build_default_tool_registry(),
                "page_relationship",
                {
                    "knowledge_unit_id": unit.id,
                    "source_page_id": source.id,
                    "target_page_id": generated.id,
                    "relation_type": "owns",
                },
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert invalid.value.code == "invalid_arguments"
