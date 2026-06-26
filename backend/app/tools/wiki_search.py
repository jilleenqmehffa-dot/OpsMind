from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import case, desc, or_, select

from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.models.wiki_page_tag import WikiPageTag
from app.models.wiki_tag import WikiTag
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.wiki_page_update import load_actor, require_actor_permission


WikiPageType = Literal["concept", "system", "process", "rule", "term", "event", "incident"]
WikiPageStatus = Literal["draft", "published", "archived"]


class WikiSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    page_type: WikiPageType | None = None
    status: WikiPageStatus = "published"
    category_id: int | None = Field(default=None, ge=1)
    tag_id: int | None = Field(default=None, ge=1)
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    limit: int = Field(default=10, ge=1, le=50)
    max_summary_chars: int = Field(default=300, ge=100, le=1000)
    max_relationships_per_page: int = Field(default=5, ge=0, le=10)

    @model_validator(mode="after")
    def validate_search(self) -> "WikiSearchInput":
        self.query = " ".join(self.query.split())
        if not self.query:
            raise ValueError("query cannot be empty")
        if self.updated_from is not None and self.updated_to is not None and self.updated_from > self.updated_to:
            raise ValueError("updated_from cannot be later than updated_to")
        return self


class WikiSearchRelationship(BaseModel):
    relationship_id: int
    relation_type: str
    related_page_id: int
    related_page_title: str


class WikiSearchItem(BaseModel):
    page_id: int
    title: str
    slug: str
    page_type: WikiPageType
    status: WikiPageStatus
    summary: str
    category_id: int | None
    tags: list[str]
    updated_at: datetime
    relationships: list[WikiSearchRelationship]


class WikiSearchOutput(BaseModel):
    query: str
    returned_count: int
    truncated: bool
    results: list[WikiSearchItem]


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_summary(content: str, keyword: str, max_chars: int) -> str:
    compact = " ".join(content.split())
    if len(compact) <= max_chars:
        return compact
    match_index = compact.lower().find(keyword.lower())
    if match_index < 0:
        return f"{compact[: max_chars - 3]}..."
    start = max(0, match_index - max_chars // 3)
    end = min(len(compact), start + max_chars)
    start = max(0, end - max_chars)
    snippet = compact[start:end]
    if start > 0:
        snippet = f"...{snippet[3:]}"
    if end < len(compact):
        snippet = f"{snippet[:-3]}..."
    return snippet


def load_tags(context: ToolContext, page_ids: list[int]) -> dict[int, list[str]]:
    result = {page_id: [] for page_id in page_ids}
    if not page_ids:
        return result
    rows = context.db.execute(
        select(WikiPageTag.page_id, WikiTag.name)
        .join(WikiTag, WikiTag.id == WikiPageTag.tag_id)
        .where(WikiPageTag.page_id.in_(page_ids))
        .order_by(WikiTag.name)
    ).all()
    for page_id, tag_name in rows:
        result[page_id].append(tag_name)
    return result


def load_relationships(
    context: ToolContext,
    page_ids: list[int],
    per_page_limit: int,
) -> dict[int, list[WikiSearchRelationship]]:
    result = {page_id: [] for page_id in page_ids}
    if not page_ids or per_page_limit == 0:
        return result
    relationships = context.db.scalars(
        select(WikiPageRelationship)
        .where(
            or_(
                WikiPageRelationship.source_page_id.in_(page_ids),
                WikiPageRelationship.target_page_id.in_(page_ids),
            )
        )
        .order_by(desc(WikiPageRelationship.updated_at), desc(WikiPageRelationship.id))
    ).all()
    related_ids = {
        related_id
        for relationship in relationships
        for related_id in (relationship.source_page_id, relationship.target_page_id)
        if related_id not in page_ids
    } | set(page_ids)
    related_pages = {
        page.id: page.title
        for page in context.db.scalars(
            select(WikiPage).where(WikiPage.id.in_(related_ids), WikiPage.deleted_at.is_(None))
        ).all()
    }
    page_id_set = set(page_ids)
    for relationship in relationships:
        for current_page_id, related_page_id in (
            (relationship.source_page_id, relationship.target_page_id),
            (relationship.target_page_id, relationship.source_page_id),
        ):
            if current_page_id not in page_id_set or related_page_id not in related_pages:
                continue
            if len(result[current_page_id]) >= per_page_limit:
                continue
            result[current_page_id].append(
                WikiSearchRelationship(
                    relationship_id=relationship.id,
                    relation_type=relationship.relation_type,
                    related_page_id=related_page_id,
                    related_page_title=related_pages[related_page_id],
                )
            )
    return result


class WikiSearchTool:
    name = "wiki_search"
    description = "Search bounded Wiki page summaries, tags, and direct relationships without reading source chunks."
    input_model = WikiSearchInput

    def invoke(self, context: ToolContext, arguments: BaseModel) -> WikiSearchOutput:
        if not isinstance(arguments, WikiSearchInput):
            raise ToolInvocationError("invalid_arguments", "Wiki Search arguments are invalid")
        actor = load_actor(context)
        require_actor_permission(context, actor, "wiki:read")

        escaped_query = escape_like(arguments.query)
        like = f"%{escaped_query}%"
        title_match = WikiPage.title.ilike(like, escape="\\")
        content_match = WikiPage.content.ilike(like, escape="\\")
        query = select(WikiPage).where(
            WikiPage.deleted_at.is_(None),
            WikiPage.status == arguments.status,
            or_(title_match, content_match),
        )
        if arguments.page_type is not None:
            query = query.where(WikiPage.page_type == arguments.page_type)
        if arguments.category_id is not None:
            query = query.where(WikiPage.category_id == arguments.category_id)
        if arguments.tag_id is not None:
            query = query.where(
                WikiPage.id.in_(select(WikiPageTag.page_id).where(WikiPageTag.tag_id == arguments.tag_id))
            )
        if arguments.updated_from is not None:
            query = query.where(WikiPage.updated_at >= arguments.updated_from)
        if arguments.updated_to is not None:
            query = query.where(WikiPage.updated_at <= arguments.updated_to)

        pages = list(
            context.db.scalars(
                query.order_by(case((title_match, 1), else_=0).desc(), desc(WikiPage.updated_at), desc(WikiPage.id))
                .limit(arguments.limit + 1)
            ).all()
        )
        truncated = len(pages) > arguments.limit
        pages = pages[: arguments.limit]
        page_ids = [page.id for page in pages]
        tag_map = load_tags(context, page_ids)
        relationship_map = load_relationships(context, page_ids, arguments.max_relationships_per_page)
        results = [
            WikiSearchItem(
                page_id=page.id,
                title=page.title,
                slug=page.slug,
                page_type=page.page_type,
                status=page.status,
                summary=build_summary(page.content, arguments.query, arguments.max_summary_chars),
                category_id=page.category_id,
                tags=tag_map[page.id],
                updated_at=page.updated_at,
                relationships=relationship_map[page.id],
            )
            for page in pages
        ]
        return WikiSearchOutput(
            query=arguments.query,
            returned_count=len(results),
            truncated=truncated,
            results=results,
        )

    def summarize_result(self, result: BaseModel) -> dict[str, Any]:
        if not isinstance(result, WikiSearchOutput):
            return {"result_type": type(result).__name__}
        return {
            "returned_count": result.returned_count,
            "truncated": result.truncated,
            "page_ids": [item.page_id for item in result.results],
            "page_type_counts": {
                page_type: sum(item.page_type == page_type for item in result.results)
                for page_type in sorted({item.page_type for item in result.results})
            },
        }
