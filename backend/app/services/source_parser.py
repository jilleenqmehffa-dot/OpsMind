from dataclasses import dataclass, field
from pathlib import Path
import re

from app.core.config import PROJECT_ROOT, UPLOAD_STORAGE_DIR


SUPPORTED_SOURCE_EXTENSIONS = {
    ".md",
    ".txt",
}

MARKDOWN_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


class SourceParseError(Exception):
    """Base error for source parsing services."""


class UnsupportedSourceType(SourceParseError):
    """Raised when a source attachment type is not supported yet."""


class SourceReadError(SourceParseError):
    """Raised when a source attachment cannot be read."""


class SourcePathNotAllowed(SourceParseError):
    """Raised when an attachment path escapes the configured upload directory."""


@dataclass(slots=True)
class SourceSection:
    index: int
    heading: str | None
    text: str
    start_char: int
    end_char: int
    paragraph_start: int
    paragraph_end: int
    source_location: str


@dataclass(slots=True)
class SourceDocument:
    attachment_id: int
    filename: str
    content_type: str | None
    sections: list[SourceSection] = field(default_factory=list)


@dataclass(slots=True)
class ParagraphSpan:
    index: int
    start_char: int
    end_char: int


def resolve_source_path(storage_path: str) -> Path:
    path = Path(storage_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved_path = path.resolve()
    allowed_root = UPLOAD_STORAGE_DIR.resolve()
    if not resolved_path.is_relative_to(allowed_root):
        raise SourcePathNotAllowed("Source path is outside the configured upload directory")
    return resolved_path


def parse_source_document(
    attachment_id: int,
    filename: str,
    storage_path: str,
    content_type: str | None,
) -> SourceDocument:
    path = resolve_source_path(storage_path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SOURCE_EXTENSIONS:
        raise UnsupportedSourceType(f"Unsupported source type: suffix={suffix or '<none>'}")

    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SourceReadError(f"Failed to read source file: {storage_path}") from exc
    except UnicodeDecodeError as exc:
        raise SourceReadError(f"Source file is not valid UTF-8: {storage_path}") from exc

    if suffix == ".md":
        sections = parse_markdown_sections(text)
    else:
        sections = parse_txt_sections(text)

    return SourceDocument(
        attachment_id=attachment_id,
        filename=filename,
        content_type=content_type,
        sections=sections,
    )


def parse_markdown_sections(text: str) -> list[SourceSection]:
    paragraph_spans = build_paragraph_spans(text)
    line_spans = build_line_spans(text)
    boundaries: list[tuple[int, int, str | None, int]] = []
    in_code_block = False

    for line_start, line_end, line in line_spans:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        match = MARKDOWN_HEADING_RE.match(line.rstrip("\r\n"))
        if match is None:
            continue

        heading_level = len(match.group(1))
        heading = match.group(2).strip()
        boundaries.append((line_start, line_end, heading, heading_level))

    if not boundaries:
        return build_single_section(text, paragraph_spans)

    sections: list[SourceSection] = []
    first_heading_start = boundaries[0][0]
    if text[:first_heading_start].strip():
        append_section(
            sections=sections,
            text=text,
            heading=None,
            body_start=0,
            body_end=first_heading_start,
            section_start=0,
            section_end=first_heading_start,
            paragraph_spans=paragraph_spans,
        )

    for index, (heading_start, heading_end, heading, _heading_level) in enumerate(boundaries):
        next_heading_start = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        append_section(
            sections=sections,
            text=text,
            heading=heading,
            body_start=heading_end,
            body_end=next_heading_start,
            section_start=heading_start,
            section_end=next_heading_start,
            paragraph_spans=paragraph_spans,
        )

    return sections


def parse_txt_sections(text: str) -> list[SourceSection]:
    paragraph_spans = build_paragraph_spans(text)
    sections: list[SourceSection] = []

    for paragraph in paragraph_spans:
        raw_text = text[paragraph.start_char : paragraph.end_char]
        heading, body = split_txt_heading(raw_text)
        append_section(
            sections=sections,
            text=text,
            heading=heading,
            body_start=paragraph.start_char,
            body_end=paragraph.end_char,
            section_start=paragraph.start_char,
            section_end=paragraph.end_char,
            paragraph_spans=paragraph_spans,
            body_override=body,
        )

    return sections


def build_single_section(text: str, paragraph_spans: list[ParagraphSpan]) -> list[SourceSection]:
    sections: list[SourceSection] = []
    append_section(
        sections=sections,
        text=text,
        heading=None,
        body_start=0,
        body_end=len(text),
        section_start=0,
        section_end=len(text),
        paragraph_spans=paragraph_spans,
    )
    return sections


def append_section(
    *,
    sections: list[SourceSection],
    text: str,
    heading: str | None,
    body_start: int,
    body_end: int,
    section_start: int,
    section_end: int,
    paragraph_spans: list[ParagraphSpan],
    body_override: str | None = None,
) -> None:
    body = body_override if body_override is not None else text[body_start:body_end]
    body = body.strip()
    if not body:
        return

    paragraph_start, paragraph_end = find_paragraph_range(paragraph_spans, section_start, section_end)
    section_index = len(sections) + 1
    source_location = (
        f"section:{section_index}; "
        f"chars:{section_start}-{section_end}; "
        f"paragraphs:{paragraph_start}-{paragraph_end}"
    )
    sections.append(
        SourceSection(
            index=section_index,
            heading=heading,
            text=body,
            start_char=section_start,
            end_char=section_end,
            paragraph_start=paragraph_start,
            paragraph_end=paragraph_end,
            source_location=source_location,
        )
    )


def build_line_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        line_end = offset + len(line)
        spans.append((offset, line_end, line))
        offset = line_end
    if not spans and text:
        spans.append((0, len(text), text))
    return spans


def build_paragraph_spans(text: str) -> list[ParagraphSpan]:
    spans: list[ParagraphSpan] = []
    paragraph_start: int | None = None
    offset = 0

    for line in text.splitlines(keepends=True):
        line_end = offset + len(line)
        if line.strip():
            if paragraph_start is None:
                paragraph_start = offset
        elif paragraph_start is not None:
            spans.append(ParagraphSpan(index=len(spans) + 1, start_char=paragraph_start, end_char=offset))
            paragraph_start = None
        offset = line_end

    if paragraph_start is not None:
        spans.append(ParagraphSpan(index=len(spans) + 1, start_char=paragraph_start, end_char=len(text)))

    return spans


def find_paragraph_range(paragraph_spans: list[ParagraphSpan], start_char: int, end_char: int) -> tuple[int, int]:
    matched = [
        paragraph.index
        for paragraph in paragraph_spans
        if paragraph.end_char > start_char and paragraph.start_char < end_char
    ]
    if not matched:
        return 0, 0
    return matched[0], matched[-1]


def split_txt_heading(raw_text: str) -> tuple[str | None, str]:
    lines = raw_text.strip().splitlines()
    if len(lines) < 2:
        return None, raw_text

    first_line = lines[0].strip()
    if len(first_line) <= 40 and first_line.endswith((":", "：")):
        return first_line.rstrip(":：").strip(), "\n".join(lines[1:]).strip()

    return None, raw_text
