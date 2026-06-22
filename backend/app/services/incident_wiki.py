from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.incident_case import IncidentCase
from app.models.user import User
from app.models.wiki_page import WikiPage
from app.models.wiki_version import WikiVersion


class IncidentWikiConflictError(Exception):
    """The incident cannot safely create or update its linked Wiki page."""


def format_datetime(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "未记录"


def optional_text(value: str | None) -> str:
    return value or "未记录"


def render_incident_markdown(incident: IncidentCase) -> str:
    return "\n".join(
        [
            f"# {incident.title}",
            "",
            f"> 来源：故障案例 #{incident.id}",
            "",
            "## 基本信息",
            "",
            f"- 相关系统：{optional_text(incident.system_name)}",
            f"- 严重级别：{incident.severity}",
            f"- 处理状态：{incident.status}",
            f"- 发生时间：{format_datetime(incident.occurred_at)}",
            f"- 解决时间：{format_datetime(incident.resolved_at)}",
            "",
            "## 故障现象",
            "",
            incident.symptom,
            "",
            "## 故障原因",
            "",
            optional_text(incident.cause),
            "",
            "## 排查过程",
            "",
            optional_text(incident.investigation_process),
            "",
            "## 修复方案",
            "",
            optional_text(incident.solution),
            "",
            "## 复盘结论",
            "",
            optional_text(incident.review_conclusion),
            "",
        ]
    )


def next_version_number(db: Session, page_id: int) -> int:
    current = db.scalar(select(func.max(WikiVersion.version_number)).where(WikiVersion.page_id == page_id))
    return int(current or 0) + 1


def publish_incident_to_wiki(
    db: Session,
    incident: IncidentCase,
    user: User,
) -> tuple[WikiPage, str]:
    content = render_incident_markdown(incident)
    action = "updated"

    if incident.wiki_page_id is None:
        slug = f"incident-{incident.id}"
        existing_page = db.scalar(select(WikiPage).where(WikiPage.slug == slug))
        if existing_page is not None:
            raise IncidentWikiConflictError("The generated Wiki slug is already in use")

        page = WikiPage(
            title=incident.title,
            slug=slug,
            content=content,
            page_type="incident",
            status="published",
            author_user_id=user.id,
        )
        db.add(page)
        db.flush()
        incident.wiki_page_id = page.id
        action = "created"
    else:
        page = db.scalar(select(WikiPage).where(WikiPage.id == incident.wiki_page_id).with_for_update())
        if page is None or page.deleted_at is not None:
            raise IncidentWikiConflictError("The linked Wiki page is missing or deleted")
        page.title = incident.title
        page.content = content
        page.page_type = "incident"
        page.status = "published"

    db.add(
        WikiVersion(
            page_id=page.id,
            title=page.title,
            content=page.content,
            version_number=next_version_number(db, page.id),
            created_by_user_id=user.id,
        )
    )
    incident.updated_by_user_id = user.id
    return page, action
