from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.models.knowledge_unit import KnowledgeUnit
from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.wiki_page_update import load_actor, require_actor_permission


RelationType = Literal[
    "references",
    "depends_on",
    "belongs_to",
    "related_to",
    "similar_to",
    "caused_by",
    "resolved_by",
]
SYMMETRIC_RELATION_TYPES = {"related_to", "similar_to"}


class PageRelationshipInput(BaseModel):
    knowledge_unit_id: int = Field(ge=1)
    source_page_id: int = Field(ge=1)
    target_page_id: int = Field(ge=1)
    relation_type: RelationType
    description: str | None = Field(default=None, max_length=1000)


class PageRelationshipOutput(BaseModel):
    relationship_id: int
    knowledge_unit_id: int
    source_page_id: int
    target_page_id: int
    relation_type: RelationType
    source_job_id: int


def load_applied_unit(context: ToolContext, knowledge_unit_id: int) -> KnowledgeUnit:
    unit = context.db.scalar(select(KnowledgeUnit).where(KnowledgeUnit.id == knowledge_unit_id))
    if unit is None:
        raise ToolInvocationError("knowledge_unit_not_found", "Knowledge unit was not found")
    if unit.apply_status != "applied":
        raise ToolInvocationError("knowledge_unit_not_applied", "Knowledge unit must be applied before relating pages")
    return unit


def load_active_pages(context: ToolContext, source_page_id: int, target_page_id: int) -> None:
    if source_page_id == target_page_id:
        raise ToolInvocationError("self_relationship", "A Wiki page cannot relate to itself")
    page_ids = set(
        context.db.scalars(
            select(WikiPage.id).where(
                WikiPage.id.in_([source_page_id, target_page_id]),
                WikiPage.deleted_at.is_(None),
            )
        ).all()
    )
    if source_page_id not in page_ids:
        raise ToolInvocationError("source_page_not_found", "Source Wiki page was not found")
    if target_page_id not in page_ids:
        raise ToolInvocationError("target_page_not_found", "Target Wiki page was not found")


def normalize_direction(source_page_id: int, target_page_id: int, relation_type: str) -> tuple[int, int]:
    if relation_type in SYMMETRIC_RELATION_TYPES:
        return tuple(sorted((source_page_id, target_page_id)))
    return source_page_id, target_page_id


class PageRelationshipTool:
    name = "page_relationship"
    description = "Create one validated, provenance-linked relationship between active Wiki pages."
    input_model = PageRelationshipInput

    def invoke(self, context: ToolContext, arguments: BaseModel) -> PageRelationshipOutput:
        if not isinstance(arguments, PageRelationshipInput):
            raise ToolInvocationError("invalid_arguments", "Page Relationship arguments are invalid")

        actor = load_actor(context)
        require_actor_permission(context, actor, "wiki:update")
        unit = load_applied_unit(context, arguments.knowledge_unit_id)
        load_active_pages(context, arguments.source_page_id, arguments.target_page_id)

        source_page_id, target_page_id = normalize_direction(
            arguments.source_page_id,
            arguments.target_page_id,
            arguments.relation_type,
        )
        provenance_page_ids = {unit.source_page_id, unit.created_page_id} - {None}
        if not provenance_page_ids.intersection({source_page_id, target_page_id}):
            raise ToolInvocationError(
                "knowledge_unit_page_mismatch",
                "Relationship must include a page linked to the knowledge unit",
            )

        duplicate_query = select(WikiPageRelationship.id).where(
            WikiPageRelationship.relation_type == arguments.relation_type
        )
        if arguments.relation_type in SYMMETRIC_RELATION_TYPES:
            duplicate_query = duplicate_query.where(
                or_(
                    (WikiPageRelationship.source_page_id == source_page_id)
                    & (WikiPageRelationship.target_page_id == target_page_id),
                    (WikiPageRelationship.source_page_id == target_page_id)
                    & (WikiPageRelationship.target_page_id == source_page_id),
                )
            )
        else:
            duplicate_query = duplicate_query.where(
                WikiPageRelationship.source_page_id == source_page_id,
                WikiPageRelationship.target_page_id == target_page_id,
            )
        if context.db.scalar(duplicate_query) is not None:
            raise ToolInvocationError("relationship_conflict", "Wiki page relationship already exists")

        relationship = WikiPageRelationship(
            source_page_id=source_page_id,
            target_page_id=target_page_id,
            relation_type=arguments.relation_type,
            description=arguments.description,
            source_type="knowledge_compilation",
            source_job_id=unit.job_id,
            created_by_user_id=actor.id,
        )
        context.db.add(relationship)
        unit.job.relationship_count += 1
        context.db.flush()
        return PageRelationshipOutput(
            relationship_id=relationship.id,
            knowledge_unit_id=unit.id,
            source_page_id=relationship.source_page_id,
            target_page_id=relationship.target_page_id,
            relation_type=arguments.relation_type,
            source_job_id=unit.job_id,
        )

    def summarize_result(self, result: BaseModel) -> dict[str, Any]:
        if not isinstance(result, PageRelationshipOutput):
            return {"result_type": type(result).__name__}
        return result.model_dump()
