from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers mapped tables
from app.db.base import Base
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tool_invocation import ToolInvocation
from app.models.user import User
from app.models.user_role import UserRole
from app.models.wiki_category import WikiCategory
from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.models.wiki_page_tag import WikiPageTag
from app.models.wiki_tag import WikiTag
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.executor import execute_tool
from app.tools.registry import build_default_tool_registry
from app.tools.wiki_search import WikiSearchOutput


TABLES = [
    User.__table__,
    Role.__table__,
    Permission.__table__,
    UserRole.__table__,
    RolePermission.__table__,
    WikiCategory.__table__,
    WikiPage.__table__,
    WikiTag.__table__,
    WikiPageTag.__table__,
    WikiPageRelationship.__table__,
    ToolInvocation.__table__,
]


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def add_user(db: Session, *, superuser: bool = True) -> User:
    user = User(
        username="search-actor",
        password_hash="unused",
        is_active=True,
        is_superuser=superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_page(
    db: Session,
    *,
    title: str,
    slug: str,
    content: str,
    page_type: str = "concept",
    status: str = "published",
    deleted: bool = False,
) -> WikiPage:
    page = WikiPage(
        title=title,
        slug=slug,
        content=content,
        page_type=page_type,
        status=status,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(page)
    db.flush()
    return page


def test_search_returns_bounded_wiki_metadata_tags_and_relationships() -> None:
    with make_session() as db:
        actor = add_user(db)
        process = add_page(
            db,
            title="Redis 故障恢复流程",
            slug="redis-recovery",
            content="先检查 Redis 连接池，再重启故障节点并验证业务恢复。" * 20,
            page_type="process",
        )
        system = add_page(
            db,
            title="缓存集群",
            slug="cache-cluster",
            content="Redis 集群负责缓存关键业务数据。",
            page_type="system",
        )
        add_page(
            db,
            title="Redis 草稿",
            slug="redis-draft",
            content="未发布内容",
            status="draft",
        )
        add_page(
            db,
            title="Redis 已删除",
            slug="redis-deleted",
            content="已删除内容",
            deleted=True,
        )
        tag = WikiTag(name="缓存", slug="cache")
        db.add(tag)
        db.flush()
        db.add(WikiPageTag(page_id=process.id, tag_id=tag.id))
        db.add(
            WikiPageRelationship(
                source_page_id=process.id,
                target_page_id=system.id,
                relation_type="depends_on",
                source_type="manual",
            )
        )
        db.commit()

        result = execute_tool(
            build_default_tool_registry(),
            "wiki_search",
            {"query": "Redis", "max_summary_chars": 100},
            ToolContext(db=db, actor_user_id=actor.id),
        )

        assert isinstance(result, WikiSearchOutput)
        assert [item.page_id for item in result.results] == [process.id, system.id]
        assert result.results[0].tags == ["缓存"]
        assert len(result.results[0].summary) <= 100
        assert result.results[0].relationships[0].related_page_id == system.id
        assert result.results[0].relationships[0].relation_type == "depends_on"
        assert all(item.status == "published" for item in result.results)

        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "success"
        assert invocation.result_summary["page_ids"] == [process.id, system.id]
        assert "results" not in invocation.result_summary


def test_search_supports_filters_and_reports_truncation() -> None:
    with make_session() as db:
        actor = add_user(db)
        tag = WikiTag(name="数据库", slug="database")
        db.add(tag)
        db.flush()
        first = add_page(
            db,
            title="PostgreSQL 连接故障",
            slug="postgres-connection",
            content="PostgreSQL 连接数耗尽。",
            page_type="incident",
        )
        second = add_page(
            db,
            title="PostgreSQL 复制故障",
            slug="postgres-replication",
            content="PostgreSQL 复制发生延迟。",
            page_type="incident",
        )
        add_page(
            db,
            title="PostgreSQL 系统",
            slug="postgres-system",
            content="PostgreSQL 数据库系统。",
            page_type="system",
        )
        db.add_all(
            [
                WikiPageTag(page_id=first.id, tag_id=tag.id),
                WikiPageTag(page_id=second.id, tag_id=tag.id),
            ]
        )
        db.commit()

        result = execute_tool(
            build_default_tool_registry(),
            "wiki_search",
            {"query": "PostgreSQL", "page_type": "incident", "tag_id": tag.id, "limit": 1},
            ToolContext(db=db, actor_user_id=actor.id),
        )

        assert result.returned_count == 1
        assert result.truncated is True
        assert result.results[0].page_type == "incident"


def test_search_escapes_like_wildcards() -> None:
    with make_session() as db:
        actor = add_user(db)
        literal = add_page(
            db,
            title="CPU 100% 故障",
            slug="cpu-100-percent",
            content="CPU 使用率达到 100%。",
        )
        add_page(db, title="普通页面", slug="ordinary", content="没有特殊符号。")
        db.commit()

        result = execute_tool(
            build_default_tool_registry(),
            "wiki_search",
            {"query": "%"},
            ToolContext(db=db, actor_user_id=actor.id),
        )

        assert [item.page_id for item in result.results] == [literal.id]


def test_search_requires_read_permission_and_valid_input() -> None:
    with make_session() as db:
        actor = add_user(db, superuser=False)
        with pytest.raises(ToolInvocationError) as denied:
            execute_tool(
                build_default_tool_registry(),
                "wiki_search",
                {"query": "Redis"},
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert denied.value.code == "permission_denied"

        actor.is_superuser = True
        db.commit()
        with pytest.raises(ToolInvocationError) as invalid:
            execute_tool(
                build_default_tool_registry(),
                "wiki_search",
                {"query": "   "},
                ToolContext(db=db, actor_user_id=actor.id),
            )
        assert invalid.value.code == "invalid_arguments"
