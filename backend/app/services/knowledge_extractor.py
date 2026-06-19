from dataclasses import dataclass

from app.services.source_parser import SourceDocument, SourceSection


MIN_SECTION_CHARS = 30

UNIT_TYPES = {
    "concept",
    "system",
    "process",
    "rule",
    "term",
    "event",
    "incident",
}

TYPE_KEYWORDS = {
    "incident": ("故障", "异常", "报错", "失败", "影响", "原因", "恢复", "修复", "复盘"),
    "process": ("步骤", "流程", "首先", "然后", "最后", "执行", "检查", "处理", "排查"),
    "rule": ("必须", "禁止", "不得", "需要", "应当", "阈值", "条件", "限制", "规范"),
    "system": ("系统", "服务", "模块", "组件", "平台", "数据库", "Redis", "ChromaDB", "API", "网关"),
    "concept": ("定义", "概念", "原理", "机制", "是什么", "用于", "表示"),
    "event": ("发布", "上线", "变更", "迁移", "升级", "巡检", "时间", "日期"),
    "term": ("术语", "简称", "缩写", "字段", "指标", "含义", "英文名"),
}

TYPE_PRIORITY = (
    "incident",
    "process",
    "rule",
    "system",
    "concept",
    "event",
    "term",
)


@dataclass(slots=True)
class CandidateKnowledgeUnit:
    title: str
    unit_type: str
    summary: str
    content: str
    source_location: str
    confidence: float
    merge_hint_title: str | None = None


def extract_knowledge_units(document: SourceDocument) -> list[CandidateKnowledgeUnit]:
    units: list[CandidateKnowledgeUnit] = []
    seen_keys: set[tuple[str, str]] = set()

    for section in document.sections:
        unit = extract_section_unit(section)
        if unit is None:
            continue

        dedupe_key = (unit.title, unit.unit_type)
        if dedupe_key in seen_keys:
            continue

        seen_keys.add(dedupe_key)
        units.append(unit)

    return units


def extract_section_unit(section: SourceSection) -> CandidateKnowledgeUnit | None:
    text = normalize_whitespace(section.text)
    if not should_extract_section(text):
        return None

    unit_type, keyword_hits = classify_section(text, section.heading)
    title = build_title(section, unit_type)
    summary = build_summary(text)
    content = build_content(unit_type, text)
    confidence = calculate_confidence(section, keyword_hits)

    return CandidateKnowledgeUnit(
        title=title,
        unit_type=unit_type,
        summary=summary,
        content=content,
        source_location=section.source_location,
        confidence=confidence,
        merge_hint_title=section.heading,
    )


def should_extract_section(text: str) -> bool:
    if len(text) < MIN_SECTION_CHARS:
        return False

    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return False

    log_like_lines = sum(1 for line in non_empty_lines if looks_like_log_line(line))
    if log_like_lines and log_like_lines / len(non_empty_lines) >= 0.8:
        return False

    return True


def classify_section(text: str, heading: str | None) -> tuple[str, int]:
    if heading:
        heading_scores = {
            unit_type: count_keyword_hits(heading, keywords)
            for unit_type, keywords in TYPE_KEYWORDS.items()
        }
        for unit_type in TYPE_PRIORITY:
            if heading_scores[unit_type] > 0:
                return unit_type, heading_scores[unit_type]

    source = f"{heading or ''}\n{text}"
    scores = {
        unit_type: count_keyword_hits(source, keywords)
        for unit_type, keywords in TYPE_KEYWORDS.items()
    }

    for unit_type in TYPE_PRIORITY:
        if scores[unit_type] > 0:
            return unit_type, scores[unit_type]

    return "concept", 0


def count_keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def build_title(section: SourceSection, unit_type: str) -> str:
    if section.heading:
        return section.heading[:80]

    first_line = next((line.strip() for line in section.text.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:80]

    return f"{unit_type} 知识单元 {section.index}"


def build_summary(text: str) -> str:
    compact = normalize_whitespace(text)
    if len(compact) <= 120:
        return compact
    return f"{compact[:117]}..."


def build_content(unit_type: str, text: str) -> str:
    heading = content_heading(unit_type)
    return f"## {heading}\n\n{text.strip()}"


def content_heading(unit_type: str) -> str:
    headings = {
        "concept": "定义",
        "system": "系统说明",
        "process": "操作流程",
        "rule": "规则说明",
        "term": "术语定义",
        "event": "事件概述",
        "incident": "故障说明",
    }
    return headings.get(unit_type, "知识内容")


def calculate_confidence(section: SourceSection, keyword_hits: int) -> float:
    confidence = 0.55
    if section.heading:
        confidence += 0.12
    if keyword_hits >= 1:
        confidence += 0.12
    if keyword_hits >= 3:
        confidence += 0.08
    if len(section.text) >= 160:
        confidence += 0.08

    return min(round(confidence, 2), 0.9)


def normalize_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def looks_like_log_line(line: str) -> bool:
    lowered = line.lower()
    return (
        lowered.startswith(("20", "[20"))
        or "error" in lowered
        or "traceback" in lowered
        or lowered.startswith(("info ", "warn ", "debug "))
    )
