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
from app.tools.executor import execute_tool
from app.tools.knowledge_extraction import KnowledgeExtractionOutput
from app.tools.registry import build_default_tool_registry


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[WikiAttachment.__table__, ToolInvocation.__table__])
    return Session(engine)


def add_attachment(db: Session, path: Path) -> WikiAttachment:
    attachment = WikiAttachment(
        page_id=1,
        filename=path.name,
        content_type="text/markdown",
        size_bytes=path.stat().st_size,
        storage_path=str(path),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def test_knowledge_extraction_tool_returns_candidates_without_persisting_content(tmp_path, monkeypatch) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    source_path = upload_root / "operations.md"
    source_path.write_text(
        "# Redis 故障处理\n\n"
        + "Redis 连接池耗尽导致请求失败，需要检查连接数并完成修复。" * 12
        + "\n\n## 日常巡检流程\n\n每天首先检查 API 成功率，然后查看慢查询，最后记录巡检结果。",
        encoding="utf-8",
    )
    monkeypatch.setattr(source_parser, "UPLOAD_STORAGE_DIR", upload_root)

    with make_session() as db:
        attachment = add_attachment(db, source_path)
        result = execute_tool(
            build_default_tool_registry(),
            "knowledge_extraction",
            {"attachment_id": attachment.id, "max_units": 1, "max_content_chars": 200},
            ToolContext(db=db),
        )

        assert isinstance(result, KnowledgeExtractionOutput)
        assert result.total_unit_count == 2
        assert result.returned_unit_count == 1
        assert result.truncated is True
        assert result.units[0].unit_type == "incident"
        assert result.units[0].source_location.startswith("section:1;")
        assert len(result.units[0].content) == 200

        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "success"
        assert invocation.result_summary == {
            "attachment_id": attachment.id,
            "filename": "operations.md",
            "total_unit_count": 2,
            "returned_unit_count": 1,
            "type_counts": {"incident": 1},
            "truncated": True,
        }
        assert "units" not in invocation.result_summary


def test_knowledge_extraction_tool_handles_no_candidate_sections(tmp_path, monkeypatch) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    source_path = upload_root / "short.md"
    source_path.write_text("# 备注\n\n太短。", encoding="utf-8")
    monkeypatch.setattr(source_parser, "UPLOAD_STORAGE_DIR", upload_root)

    with make_session() as db:
        attachment = add_attachment(db, source_path)
        result = execute_tool(
            build_default_tool_registry(),
            "knowledge_extraction",
            {"attachment_id": attachment.id},
            ToolContext(db=db),
        )

        assert isinstance(result, KnowledgeExtractionOutput)
        assert result.total_unit_count == 0
        assert result.units == []
        assert result.truncated is False


def test_knowledge_extraction_tool_validates_limits_and_is_registered() -> None:
    registry = build_default_tool_registry()
    assert registry.names() == (
        "knowledge_extraction",
        "page_relationship",
        "source_parse",
        "wiki_page_update",
    )

    with make_session() as db:
        with pytest.raises(ToolInvocationError) as captured:
            execute_tool(
                registry,
                "knowledge_extraction",
                {"attachment_id": 1, "max_units": 0},
                ToolContext(db=db),
            )

        assert captured.value.code == "invalid_arguments"
        invocation = db.scalar(select(ToolInvocation))
        assert invocation.status == "failed"
        assert invocation.error_code == "invalid_arguments"
