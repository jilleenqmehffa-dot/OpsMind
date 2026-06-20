from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers all mapped tables for the test database
from app.db.base import Base
from app.models.wiki_page import WikiPage
from app.models.wiki_version import WikiVersion
from app.services.llm_provider import LLMProviderError, LLMResult, LLMUsage
from app.services.wiki_qa import WikiQuestionError, answer_wiki_question


class StubProvider:
    provider_name = "stub"
    model = "stub-model"

    def __init__(self, content: str = "先检查复制延迟指标。[Wiki:1]") -> None:
        self.content = content
        self.calls = []

    def generate(self, messages, **kwargs) -> LLMResult:
        self.calls.append((messages, kwargs))
        return LLMResult(
            content=self.content,
            provider=self.provider_name,
            model=self.model,
            usage=LLMUsage(prompt_tokens=30, completion_tokens=8),
            duration_ms=12,
            finish_reason="stop",
        )


class FailingProvider(StubProvider):
    def generate(self, messages, **kwargs) -> LLMResult:
        raise LLMProviderError("provider unavailable")


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    table_names = (
        "users",
        "wiki_categories",
        "wiki_pages",
        "wiki_versions",
        "wiki_page_relationships",
    )
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in table_names])
    return Session(engine)


def add_page(db: Session) -> WikiPage:
    now = datetime.now(timezone.utc)
    page = WikiPage(
        title="PostgreSQL 主从延迟排查",
        slug="postgres-replication-lag",
        content="先检查复制延迟指标，再检查 WAL 堆积和网络状态。",
        status="published",
        updated_at=now,
    )
    db.add(page)
    db.flush()
    db.add(
        WikiVersion(
            page_id=page.id,
            title=page.title,
            content=page.content,
            version_number=1,
            created_at=now,
        )
    )
    db.commit()
    return page


def test_answer_uses_context_and_returns_normalized_metadata() -> None:
    with make_session() as db:
        page = add_page(db)
        provider = StubProvider(content=f"先检查复制延迟指标。[Wiki:{page.id}]")

        response = answer_wiki_question(db, "如何排查 PostgreSQL 延迟？", provider=provider)

        assert response.answer.endswith(f"[Wiki:{page.id}]")
        assert [citation.page_id for citation in response.citations] == [page.id]
        assert response.insufficient_knowledge is False
        assert response.metadata.provider == "stub"
        assert response.metadata.model == "stub-model"
        assert response.metadata.duration_ms == 12
        assert response.metadata.total_tokens == 38
        messages, kwargs = provider.calls[0]
        assert kwargs == {}
        assert messages[0].role == "system"
        assert "只能依据" in messages[0].content
        assert page.content in messages[1].content


def test_answer_skips_provider_when_context_is_insufficient() -> None:
    with make_session() as db:
        provider = StubProvider()

        response = answer_wiki_question(db, "完全不存在的知识", provider=provider)

        assert response.insufficient_knowledge is True
        assert response.citations == []
        assert response.metadata.provider == "not_called"
        assert response.metadata.total_tokens == 0
        assert provider.calls == []


def test_answer_rejects_citation_outside_context() -> None:
    with make_session() as db:
        add_page(db)

        with pytest.raises(WikiQuestionError, match="outside the context"):
            answer_wiki_question(
                db,
                "如何排查 PostgreSQL 延迟？",
                provider=StubProvider(content="错误引用。[Wiki:999]"),
            )


def test_answer_converts_provider_error() -> None:
    with make_session() as db:
        add_page(db)

        with pytest.raises(WikiQuestionError, match="failed to generate"):
            answer_wiki_question(
                db,
                "如何排查 PostgreSQL 延迟？",
                provider=FailingProvider(),
            )


def test_answer_rejects_empty_provider_result() -> None:
    with make_session() as db:
        add_page(db)

        with pytest.raises(WikiQuestionError, match="empty Wiki answer"):
            answer_wiki_question(
                db,
                "如何排查 PostgreSQL 延迟？",
                provider=StubProvider(content="   "),
            )
