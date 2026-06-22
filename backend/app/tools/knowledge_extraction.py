from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from app.services.knowledge_extractor import extract_knowledge_units
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.source_parse import load_source_document


class KnowledgeExtractionInput(BaseModel):
    attachment_id: int = Field(ge=1)
    max_units: int = Field(default=20, ge=1, le=50)
    max_content_chars: int = Field(default=4000, ge=200, le=8000)


class ExtractedKnowledgeUnit(BaseModel):
    title: str
    unit_type: str
    summary: str
    content: str
    source_location: str
    confidence: float
    merge_hint_title: str | None
    truncated: bool


class KnowledgeExtractionOutput(BaseModel):
    attachment_id: int
    filename: str
    total_unit_count: int
    returned_unit_count: int
    truncated: bool
    units: list[ExtractedKnowledgeUnit]


class KnowledgeExtractionTool:
    name = "knowledge_extraction"
    description = "Extract bounded candidate knowledge units from a local Wiki attachment without writing Wiki data."
    input_model = KnowledgeExtractionInput

    def invoke(self, context: ToolContext, arguments: BaseModel) -> KnowledgeExtractionOutput:
        if not isinstance(arguments, KnowledgeExtractionInput):
            raise ToolInvocationError("invalid_arguments", "Knowledge Extraction arguments are invalid")

        document = load_source_document(context, arguments.attachment_id)
        candidates = extract_knowledge_units(document)
        selected_candidates = candidates[: arguments.max_units]
        units = [
            ExtractedKnowledgeUnit(
                title=candidate.title,
                unit_type=candidate.unit_type,
                summary=candidate.summary,
                content=candidate.content[: arguments.max_content_chars],
                source_location=candidate.source_location,
                confidence=candidate.confidence,
                merge_hint_title=candidate.merge_hint_title,
                truncated=len(candidate.content) > arguments.max_content_chars,
            )
            for candidate in selected_candidates
        ]
        truncated = len(candidates) > len(selected_candidates) or any(unit.truncated for unit in units)
        return KnowledgeExtractionOutput(
            attachment_id=document.attachment_id,
            filename=document.filename,
            total_unit_count=len(candidates),
            returned_unit_count=len(units),
            truncated=truncated,
            units=units,
        )

    def summarize_result(self, result: BaseModel) -> dict[str, Any]:
        if not isinstance(result, KnowledgeExtractionOutput):
            return {"result_type": type(result).__name__}
        type_counts = Counter(unit.unit_type for unit in result.units)
        return {
            "attachment_id": result.attachment_id,
            "filename": result.filename,
            "total_unit_count": result.total_unit_count,
            "returned_unit_count": result.returned_unit_count,
            "type_counts": dict(sorted(type_counts.items())),
            "truncated": result.truncated,
        }
