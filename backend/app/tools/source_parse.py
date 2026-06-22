from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.wiki_attachment import WikiAttachment
from app.services.source_parser import (
    SourceDocument,
    SourceParseError,
    SourcePathNotAllowed,
    SourceReadError,
    UnsupportedSourceType,
    parse_source_document,
)
from app.tools.base import ToolContext, ToolInvocationError


class SourceParseInput(BaseModel):
    attachment_id: int = Field(ge=1)
    max_sections: int = Field(default=20, ge=1, le=50)
    max_chars_per_section: int = Field(default=4000, ge=200, le=8000)


class ParsedSourceSection(BaseModel):
    index: int
    heading: str | None
    text: str
    source_location: str
    truncated: bool


class SourceParseOutput(BaseModel):
    attachment_id: int
    filename: str
    content_type: str | None
    total_section_count: int
    returned_section_count: int
    truncated: bool
    sections: list[ParsedSourceSection]


def load_source_document(context: ToolContext, attachment_id: int) -> SourceDocument:
    attachment = context.db.scalar(select(WikiAttachment).where(WikiAttachment.id == attachment_id))
    if attachment is None:
        raise ToolInvocationError("attachment_not_found", "Attachment was not found")

    try:
        return parse_source_document(
            attachment_id=attachment.id,
            filename=attachment.filename,
            storage_path=attachment.storage_path,
            content_type=attachment.content_type,
        )
    except UnsupportedSourceType as exc:
        raise ToolInvocationError("unsupported_source_type", "Attachment type is not supported") from exc
    except SourcePathNotAllowed as exc:
        raise ToolInvocationError("source_path_not_allowed", "Attachment path is not allowed") from exc
    except SourceReadError as exc:
        raise ToolInvocationError("source_read_failed", "Attachment could not be read") from exc
    except SourceParseError as exc:
        raise ToolInvocationError("source_parse_failed", "Attachment parsing failed") from exc


class SourceParseTool:
    name = "source_parse"
    description = "Parse a local Wiki attachment into bounded, traceable text sections."
    input_model = SourceParseInput

    def invoke(self, context: ToolContext, arguments: BaseModel) -> SourceParseOutput:
        if not isinstance(arguments, SourceParseInput):
            raise ToolInvocationError("invalid_arguments", "Source Parse arguments are invalid")

        document = load_source_document(context, arguments.attachment_id)

        selected_sections = document.sections[: arguments.max_sections]
        sections = [
            ParsedSourceSection(
                index=section.index,
                heading=section.heading,
                text=section.text[: arguments.max_chars_per_section],
                source_location=section.source_location,
                truncated=len(section.text) > arguments.max_chars_per_section,
            )
            for section in selected_sections
        ]
        truncated = len(document.sections) > len(selected_sections) or any(section.truncated for section in sections)
        return SourceParseOutput(
            attachment_id=document.attachment_id,
            filename=document.filename,
            content_type=document.content_type,
            total_section_count=len(document.sections),
            returned_section_count=len(sections),
            truncated=truncated,
            sections=sections,
        )

    def summarize_result(self, result: BaseModel) -> dict[str, Any]:
        if not isinstance(result, SourceParseOutput):
            return {"result_type": type(result).__name__}
        return {
            "attachment_id": result.attachment_id,
            "filename": result.filename,
            "total_section_count": result.total_section_count,
            "returned_section_count": result.returned_section_count,
            "truncated": result.truncated,
        }
