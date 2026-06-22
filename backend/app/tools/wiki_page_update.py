from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.models.knowledge_unit import KnowledgeUnit
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.models.wiki_page import WikiPage
from app.models.wiki_version import WikiVersion
from app.tools.base import ToolContext, ToolInvocationError


MAX_UNIT_CONTENT_CHARS = 100_000
MAX_PAGE_CONTENT_CHARS = 200_000


class WikiPageUpdateInput(BaseModel):
    knowledge_unit_id: int = Field(ge=1)
    action: Literal["create", "update", "skip"]
    target_page_id: int | None = Field(default=None, ge=1)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=220,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    update_mode: Literal["append", "replace"] | None = None
    review_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_action_arguments(self) -> "WikiPageUpdateInput":
        if self.action == "create":
            if self.slug is None:
                raise ValueError("slug is required when action is create")
            if self.target_page_id is not None or self.update_mode is not None:
                raise ValueError("create does not accept target_page_id or update_mode")
        elif self.action == "update":
            if self.target_page_id is None or self.update_mode is None:
                raise ValueError("target_page_id and update_mode are required when action is update")
            if self.slug is not None:
                raise ValueError("update does not accept slug")
        elif self.target_page_id is not None or self.slug is not None or self.update_mode is not None:
            raise ValueError("skip does not accept target_page_id, slug, or update_mode")
        return self


class WikiPageUpdateOutput(BaseModel):
    knowledge_unit_id: int
    action: Literal["create", "update", "skip"]
    apply_status: Literal["applied", "skipped"]
    page_id: int | None
    version_number: int | None
    source_attachment_id: int
    source_job_id: int


def load_actor(context: ToolContext) -> User:
    if context.actor_user_id is None:
        raise ToolInvocationError("actor_required", "Knowledge write tools require an authenticated actor")
    actor = context.db.scalar(select(User).where(User.id == context.actor_user_id))
    if actor is None or not actor.is_active:
        raise ToolInvocationError("actor_not_allowed", "Tool actor is missing or inactive")
    return actor


def require_actor_permission(context: ToolContext, actor: User, permission_code: str) -> None:
    if actor.is_superuser:
        return
    permission = context.db.scalar(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == actor.id, Permission.code == permission_code)
    )
    if permission is None:
        raise ToolInvocationError("permission_denied", f"Actor lacks required permission: {permission_code}")


def load_pending_unit(context: ToolContext, knowledge_unit_id: int) -> KnowledgeUnit:
    unit = context.db.scalar(select(KnowledgeUnit).where(KnowledgeUnit.id == knowledge_unit_id))
    if unit is None:
        raise ToolInvocationError("knowledge_unit_not_found", "Knowledge unit was not found")
    if unit.apply_status != "pending":
        raise ToolInvocationError("knowledge_unit_already_reviewed", "Knowledge unit is no longer pending")
    if len(unit.content) > MAX_UNIT_CONTENT_CHARS:
        raise ToolInvocationError("content_too_large", "Knowledge unit content exceeds the write limit")
    return unit


def load_target_page(context: ToolContext, page_id: int) -> WikiPage:
    page = context.db.scalar(
        select(WikiPage).where(WikiPage.id == page_id, WikiPage.deleted_at.is_(None))
    )
    if page is None:
        raise ToolInvocationError("wiki_page_not_found", "Target Wiki page was not found")
    return page


def next_version_number(context: ToolContext, page_id: int) -> int:
    current = context.db.scalar(
        select(func.max(WikiVersion.version_number)).where(WikiVersion.page_id == page_id)
    )
    return int(current or 0) + 1


def add_version(context: ToolContext, page: WikiPage, actor: User) -> WikiVersion:
    version = WikiVersion(
        page_id=page.id,
        title=page.title,
        content=page.content,
        version_number=next_version_number(context, page.id),
        created_by_user_id=actor.id,
    )
    context.db.add(version)
    return version


class WikiPageUpdateTool:
    name = "wiki_page_update"
    description = (
        "Create, explicitly append to or replace, or skip a Wiki page from one persisted pending knowledge unit."
    )
    input_model = WikiPageUpdateInput

    def invoke(self, context: ToolContext, arguments: BaseModel) -> WikiPageUpdateOutput:
        if not isinstance(arguments, WikiPageUpdateInput):
            raise ToolInvocationError("invalid_arguments", "Wiki Page Update arguments are invalid")

        actor = load_actor(context)
        permission_code = "wiki:create" if arguments.action == "create" else "wiki:update"
        require_actor_permission(context, actor, permission_code)
        unit = load_pending_unit(context, arguments.knowledge_unit_id)

        if arguments.action == "skip":
            unit.apply_status = "skipped"
            unit.review_note = arguments.review_note
            return WikiPageUpdateOutput(
                knowledge_unit_id=unit.id,
                action="skip",
                apply_status="skipped",
                page_id=None,
                version_number=None,
                source_attachment_id=unit.source_attachment_id,
                source_job_id=unit.job_id,
            )

        if arguments.action == "create":
            existing_slug = context.db.scalar(select(WikiPage.id).where(WikiPage.slug == arguments.slug))
            if existing_slug is not None:
                raise ToolInvocationError("slug_conflict", "Wiki page slug already exists")
            page = WikiPage(
                title=unit.title,
                slug=arguments.slug,
                content=unit.content,
                page_type=unit.unit_type,
                status="draft",
                author_user_id=actor.id,
            )
            context.db.add(page)
            context.db.flush()
            version = add_version(context, page, actor)
            unit.job.created_page_count += 1
        else:
            page = load_target_page(context, arguments.target_page_id)
            if arguments.update_mode == "replace":
                updated_content = unit.content
            else:
                separator = "\n\n" if page.content.rstrip() else ""
                updated_content = f"{page.content.rstrip()}{separator}## {unit.title}\n\n{unit.content}"
            if len(updated_content) > MAX_PAGE_CONTENT_CHARS:
                raise ToolInvocationError("content_too_large", "Updated Wiki page exceeds the write limit")
            page.content = updated_content
            version = add_version(context, page, actor)
            unit.job.updated_page_count += 1

        unit.apply_status = "applied"
        unit.created_page_id = page.id
        unit.review_note = arguments.review_note
        context.db.flush()
        return WikiPageUpdateOutput(
            knowledge_unit_id=unit.id,
            action=arguments.action,
            apply_status="applied",
            page_id=page.id,
            version_number=version.version_number,
            source_attachment_id=unit.source_attachment_id,
            source_job_id=unit.job_id,
        )

    def summarize_result(self, result: BaseModel) -> dict[str, Any]:
        if not isinstance(result, WikiPageUpdateOutput):
            return {"result_type": type(result).__name__}
        return {
            "knowledge_unit_id": result.knowledge_unit_id,
            "action": result.action,
            "apply_status": result.apply_status,
            "page_id": result.page_id,
            "version_number": result.version_number,
            "source_attachment_id": result.source_attachment_id,
            "source_job_id": result.source_job_id,
        }
