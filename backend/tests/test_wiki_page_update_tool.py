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
from app.models.wiki_version import WikiVersion
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.executor import execute_tool
from app.tools.registry import build_default_tool_registry
from app.tools.wiki_page_update import WikiPageUpdateOutput


TABLES = [
    User.__table__,
    Role.__table__,
    Permission.__table__,
    UserRole.__table__,
    RolePermission.__table__,
    WikiPage.__table__,
    WikiVersion.__table__,
    WikiAttachment.__table__,
    KnowledgeCompilationJob.__table__,
    KnowledgeUnit.__table__,
    ToolInvocation.__table__,
]


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def seed_unit(db: Session, *, superuser: bool = True) -> tuple[User, KnowledgeUnit]:
    actor = User(
        username="tool-actor",
        password_hash="unused",
        is_active=True,
        is_superuser=superuser,
    )
    source_page = WikiPage(
        title="Source",
        slug="source",
        content="Source content",
        page_type="system",
        status="draft",
        author=actor,
    )
    db.add_all([actor, source_page])
    db.flush()
    attachment = WikiAttachment(
        page_id=source_page.id,
        filename="source.md",
        content_type="text/markdown",
        size_bytes=100,
        storage_path="backend/storage/uploads/source.md",
        uploaded_by_user_id=actor.id,
    )
    db.add(attachment)
    db.flush()
    job = KnowledgeCompilationJob(
        page_id=source_page.id,
        attachment_id=attachment.id,
        status="ready",
        knowledge_unit_count=1,
    )
    db.add(job)
    db.flush()
    unit = KnowledgeUnit(
        job_id=job.id,
        source_attachment_id=attachment.id,
        source_page_id=source_page.id,
        title="Redis recovery",
        unit_type="process",
        summary="Recovery summary",
        content="Check connections, restart safely, and verify recovery.",
        source_location="section:1;heading:Redis recovery",
        confidence=0.9,
        apply_status="pending",
    )
    db.add(unit)
    db.commit()
    db.refresh(actor)
    db.refresh(unit)
    return actor, unit


def test_create_page_from_persisted_unit_with_version_and_provenance() -> None:
    with make_session() as db:
        actor, unit = seed_unit(db)
        result = execute_tool(
            build_default_tool_registry(),
            "wiki_page_update",
            {
                "knowledge_unit_id": unit.id,
                "action": "create",
                "slug": "redis-recovery",
                "review_note": "Approved for a draft page",
            },
            ToolContext(db=db, actor_user_id=actor.id),
        )

        assert isinstance(result, WikiPageUpdateOutput)
        assert result.action == "create"
        assert result.version_number == 1
        page = db.get(WikiPage, result.page_id)
        assert page.title == unit.title
        assert page.content == unit.content
        assert page.page_type == unit.unit_type
        assert page.status == "draft"

        db.refresh(unit)
        db.refresh(unit.job)
        assert unit.apply_status == "applied"
        assert unit.created_page_id == page.id
        assert unit.job.created_page_count == 1
        version = db.scalar(select(WikiVersion).where(WikiVersion.page_id == page.id))
        assert version.version_number == 1
        assert version.content == unit.content

        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "success"
        assert invocation.result_summary["source_attachment_id"] == unit.source_attachment_id
        assert invocation.result_summary["source_job_id"] == unit.job_id


@pytest.mark.parametrize(
    ("update_mode", "expected_content"),
    [
        (
            "append",
            "Existing page content\n\n## Redis recovery\n\nCheck connections, restart safely, and verify recovery.",
        ),
        ("replace", "Check connections, restart safely, and verify recovery."),
    ],
)
def test_update_page_requires_explicit_merge_mode(update_mode: str, expected_content: str) -> None:
    with make_session() as db:
        actor, unit = seed_unit(db)
        target = WikiPage(
            title="Existing target",
            slug=f"target-{update_mode}",
            content="Existing page content",
            page_type="system",
            status="published",
            author_user_id=actor.id,
        )
        db.add(target)
        db.flush()
        db.add(
            WikiVersion(
                page_id=target.id,
                title=target.title,
                content=target.content,
                version_number=1,
                created_by_user_id=actor.id,
            )
        )
        db.commit()

        result = execute_tool(
            build_default_tool_registry(),
            "wiki_page_update",
            {
                "knowledge_unit_id": unit.id,
                "action": "update",
                "target_page_id": target.id,
                "update_mode": update_mode,
            },
            ToolContext(db=db, actor_user_id=actor.id),
        )

        db.refresh(target)
        db.refresh(unit.job)
        assert result.version_number == 2
        assert target.content == expected_content
        assert target.status == "published"
        assert unit.job.updated_page_count == 1
        versions = db.scalars(
            select(WikiVersion).where(WikiVersion.page_id == target.id).order_by(WikiVersion.version_number)
        ).all()
        assert [version.version_number for version in versions] == [1, 2]


def test_skip_marks_unit_without_writing_a_page() -> None:
    with make_session() as db:
        actor, unit = seed_unit(db)
        page_count_before = len(db.scalars(select(WikiPage)).all())

        result = execute_tool(
            build_default_tool_registry(),
            "wiki_page_update",
            {"knowledge_unit_id": unit.id, "action": "skip", "review_note": "Duplicate knowledge"},
            ToolContext(db=db, actor_user_id=actor.id),
        )

        db.refresh(unit)
        assert result.apply_status == "skipped"
        assert result.page_id is None
        assert unit.review_note == "Duplicate knowledge"
        assert len(db.scalars(select(WikiPage)).all()) == page_count_before


def test_write_requires_actor_permission_and_records_failure() -> None:
    with make_session() as db:
        actor, unit = seed_unit(db, superuser=False)

        with pytest.raises(ToolInvocationError) as captured:
            execute_tool(
                build_default_tool_registry(),
                "wiki_page_update",
                {"knowledge_unit_id": unit.id, "action": "create", "slug": "denied-page"},
                ToolContext(db=db, actor_user_id=actor.id),
            )

        assert captured.value.code == "permission_denied"
        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "failed"
        assert invocation.error_code == "permission_denied"
        assert db.scalar(select(WikiPage).where(WikiPage.slug == "denied-page")) is None


def test_invalid_action_arguments_and_replay_are_rejected() -> None:
    with make_session() as db:
        actor, unit = seed_unit(db)
        with pytest.raises(ToolInvocationError) as invalid:
            execute_tool(
                build_default_tool_registry(),
                "wiki_page_update",
                {"knowledge_unit_id": unit.id, "action": "update", "target_page_id": 1},
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert invalid.value.code == "invalid_arguments"

        unit.apply_status = "skipped"
        db.commit()
        with pytest.raises(ToolInvocationError) as replay:
            execute_tool(
                build_default_tool_registry(),
                "wiki_page_update",
                {"knowledge_unit_id": unit.id, "action": "skip"},
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert replay.value.code == "knowledge_unit_already_reviewed"
