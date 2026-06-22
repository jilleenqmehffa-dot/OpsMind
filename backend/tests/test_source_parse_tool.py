from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers mapped tables
from app.db.base import Base
from app.models.tool_invocation import ToolInvocation
from app.models.wiki_attachment import WikiAttachment
from app.services import source_parser
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.executor import execute_tool, sanitize_summary
from app.tools.registry import ToolRegistry, build_default_tool_registry
from app.tools.source_parse import SourceParseOutput, SourceParseTool


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[WikiAttachment.__table__, ToolInvocation.__table__],
    )
    return Session(engine)


def add_attachment(db: Session, path: Path, *, filename: str = "guide.md") -> WikiAttachment:
    attachment = WikiAttachment(
        page_id=1,
        filename=filename,
        content_type="text/markdown",
        size_bytes=path.stat().st_size,
        storage_path=str(path),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def test_source_parse_tool_returns_bounded_sections_and_safe_audit(tmp_path, monkeypatch) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    source_path = upload_root / "guide.md"
    source_path.write_text(
        "# Redis 故障\n\n" + "连接池耗尽导致请求失败。" * 30 + "\n\n## 处理步骤\n\n扩容连接池并检查恢复。",
        encoding="utf-8",
    )
    monkeypatch.setattr(source_parser, "UPLOAD_STORAGE_DIR", upload_root)

    with make_session() as db:
        attachment = add_attachment(db, source_path)
        result = execute_tool(
            build_default_tool_registry(),
            "source_parse",
            {"attachment_id": attachment.id, "max_sections": 1, "max_chars_per_section": 200},
            ToolContext(db=db),
        )

        assert isinstance(result, SourceParseOutput)
        assert result.total_section_count == 2
        assert result.returned_section_count == 1
        assert result.truncated is True
        assert len(result.sections[0].text) == 200

        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "success"
        assert invocation.tool_name == "source_parse"
        assert invocation.result_summary == {
            "attachment_id": attachment.id,
            "filename": "guide.md",
            "total_section_count": 2,
            "returned_section_count": 1,
            "truncated": True,
        }
        assert "sections" not in invocation.result_summary


def test_source_parse_tool_rejects_path_outside_upload_root(tmp_path, monkeypatch) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside_path = tmp_path / "secret.md"
    outside_path.write_text("# 不允许读取\n\n敏感内容。", encoding="utf-8")
    monkeypatch.setattr(source_parser, "UPLOAD_STORAGE_DIR", upload_root)

    with make_session() as db:
        attachment = add_attachment(db, outside_path, filename="secret.md")
        with pytest.raises(ToolInvocationError) as captured:
            execute_tool(
                build_default_tool_registry(),
                "source_parse",
                {"attachment_id": attachment.id},
                ToolContext(db=db),
            )

        assert captured.value.code == "source_path_not_allowed"
        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "failed"
        assert invocation.error_code == "source_path_not_allowed"
        assert invocation.result_summary is None


def test_source_parse_tool_records_missing_attachment_failure() -> None:
    with make_session() as db:
        with pytest.raises(ToolInvocationError) as captured:
            execute_tool(
                build_default_tool_registry(),
                "source_parse",
                {"attachment_id": 999},
                ToolContext(db=db),
            )

        assert captured.value.code == "attachment_not_found"
        invocation = db.scalar(select(ToolInvocation))
        assert invocation.input_summary == {"attachment_id": 999}
        assert invocation.error_code == "attachment_not_found"


def test_registry_rejects_duplicates_and_audits_unknown_tool() -> None:
    registry = ToolRegistry()
    registry.register(SourceParseTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(SourceParseTool())

    with make_session() as db:
        with pytest.raises(ToolInvocationError) as captured:
            execute_tool(registry, "shell", {}, ToolContext(db=db))
        assert captured.value.code == "tool_not_found"
        invocation = db.scalar(select(ToolInvocation))
        assert invocation.tool_name == "shell"
        assert invocation.error_code == "tool_not_found"


def test_audit_summary_redacts_secrets_and_limits_strings() -> None:
    summary = sanitize_summary({"access_token": "secret-value", "query": "x" * 250})

    assert summary["access_token"] == "[REDACTED]"
    assert summary["query"].endswith("...")
    assert len(summary["query"]) == 203
