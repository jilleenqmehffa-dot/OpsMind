from app.services.knowledge_extractor import extract_knowledge_units
from app.services.source_parser import SourceDocument, parse_markdown_sections, parse_txt_sections


def test_extract_units_from_markdown_sections() -> None:
    text = """# 支付系统巡检流程

每天上午需要检查支付 API 成功率、Redis 连接数和数据库慢查询。
如果成功率低于阈值，需要先检查网关日志，然后排查支付服务错误码。

## 故障处理

支付接口报错会影响订单创建，需要先定位异常原因，修复后确认成功率恢复。
"""

    document = SourceDocument(
        attachment_id=1,
        filename="demo.md",
        content_type="text/markdown",
        sections=parse_markdown_sections(text),
    )

    units = extract_knowledge_units(document)

    assert len(units) == 2
    assert units[0].title == "支付系统巡检流程"
    assert units[0].unit_type == "process"
    assert units[0].source_location.startswith("section:1;")
    assert units[1].title == "故障处理"
    assert units[1].unit_type == "incident"
    assert units[1].source_location.startswith("section:2;")


def test_extract_units_from_txt_heading_paragraphs() -> None:
    text = """故障现象：
支付接口大量失败，影响订单创建，需要检查网关日志和支付服务异常。

处理步骤：
首先检查 API 成功率，然后排查 Redis 连接数，最后确认服务恢复。
"""

    document = SourceDocument(
        attachment_id=2,
        filename="incident.txt",
        content_type="text/plain",
        sections=parse_txt_sections(text),
    )

    units = extract_knowledge_units(document)

    assert len(units) == 2
    assert units[0].title == "故障现象"
    assert units[0].unit_type == "incident"
    assert units[1].title == "处理步骤"
    assert units[1].unit_type == "process"


def test_skip_short_sections() -> None:
    document = SourceDocument(
        attachment_id=3,
        filename="short.txt",
        content_type="text/plain",
        sections=parse_txt_sections("备注：\n太短。"),
    )

    assert extract_knowledge_units(document) == []
