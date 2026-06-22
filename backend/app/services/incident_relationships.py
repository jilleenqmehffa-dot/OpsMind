from dataclasses import dataclass, field
from hashlib import sha256
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.incident_case import IncidentCase
from app.models.user import User
from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.models.wiki_version import WikiVersion
from app.services.incident_wiki import next_version_number


class IncidentRelationshipConflictError(Exception):
    """Generated knowledge would overwrite a page not owned by this workflow."""


@dataclass
class IncidentRelationshipBuildResult:
    incident_id: int
    wiki_page_id: int
    created_page_ids: list[int] = field(default_factory=list)
    updated_page_ids: list[int] = field(default_factory=list)
    relationship_ids: list[int] = field(default_factory=list)
    similar_incident_ids: list[int] = field(default_factory=list)


def normalize_text(value: str | None) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").lower())


def text_similarity(left: str, right: str) -> float:
    left_chars = set(normalize_text(left))
    right_chars = set(normalize_text(right))
    if not left_chars or not right_chars:
        return 0.0
    return len(left_chars & right_chars) / len(left_chars | right_chars)


def incident_similarity(left: IncidentCase, right: IncidentCase) -> float:
    left_system = normalize_text(left.system_name)
    right_system = normalize_text(right.system_name)
    if not left_system or left_system != right_system:
        return 0.0
    content_score = text_similarity(f"{left.title}{left.symptom}", f"{right.title}{right.symptom}")
    return 0.5 + 0.5 * content_score


def add_version(db: Session, page: WikiPage, user: User) -> None:
    db.add(
        WikiVersion(
            page_id=page.id,
            title=page.title,
            content=page.content,
            version_number=next_version_number(db, page.id),
            created_by_user_id=user.id,
        )
    )


def upsert_relationship(
    db: Session,
    *,
    source_page_id: int,
    target_page_id: int,
    relation_type: str,
    description: str,
    user: User,
) -> WikiPageRelationship:
    relationship = db.scalar(
        select(WikiPageRelationship).where(
            WikiPageRelationship.source_page_id == source_page_id,
            WikiPageRelationship.target_page_id == target_page_id,
            WikiPageRelationship.relation_type == relation_type,
        )
    )
    if relationship is None:
        relationship = WikiPageRelationship(
            source_page_id=source_page_id,
            target_page_id=target_page_id,
            relation_type=relation_type,
            description=description,
            source_type="incident_case",
            created_by_user_id=user.id,
        )
        db.add(relationship)
        db.flush()
    elif relationship.source_type == "incident_case":
        relationship.description = description
    return relationship


def upsert_generated_page(
    db: Session,
    *,
    incident_page: WikiPage,
    slug: str,
    title: str,
    content: str,
    page_type: str,
    relation_type: str,
    description: str,
    user: User,
    allow_shared: bool = False,
) -> tuple[WikiPage, WikiPageRelationship, str]:
    owned_relationship = db.scalar(
        select(WikiPageRelationship).where(
            WikiPageRelationship.source_page_id == incident_page.id,
            WikiPageRelationship.relation_type == relation_type,
            WikiPageRelationship.source_type == "incident_case",
        )
    )
    page = owned_relationship.target_page if owned_relationship is not None else None
    if page is None:
        existing = db.scalar(select(WikiPage).where(WikiPage.slug == slug))
        if existing is not None:
            if not allow_shared or existing.page_type != page_type or existing.title != title or existing.deleted_at is not None:
                raise IncidentRelationshipConflictError(f"Generated Wiki slug '{slug}' is already in use")
            page = existing
        else:
            page = WikiPage(
                title=title,
                slug=slug,
                content=content,
                page_type=page_type,
                status="published",
                author_user_id=user.id,
            )
            db.add(page)
            db.flush()
            add_version(db, page, user)
            state = "created"
            relationship = upsert_relationship(
                db,
                source_page_id=incident_page.id,
                target_page_id=page.id,
                relation_type=relation_type,
                description=description,
                user=user,
            )
            return page, relationship, state

    if page.deleted_at is not None or page.slug != slug or page.page_type != page_type:
        raise IncidentRelationshipConflictError("The generated page link is inconsistent or deleted")

    changed = page.title != title or page.content != content or page.status != "published"
    if changed:
        page.title = title
        page.content = content
        page.status = "published"
        add_version(db, page, user)
    relationship = upsert_relationship(
        db,
        source_page_id=incident_page.id,
        target_page_id=page.id,
        relation_type=relation_type,
        description=description,
        user=user,
    )
    return page, relationship, "updated" if changed else "unchanged"


def build_incident_relationships(
    db: Session,
    incident: IncidentCase,
    user: User,
    *,
    similarity_threshold: float = 0.62,
) -> IncidentRelationshipBuildResult:
    if incident.wiki_page_id is None:
        raise IncidentRelationshipConflictError("Publish the incident to Wiki before building relationships")
    incident_page = db.scalar(select(WikiPage).where(WikiPage.id == incident.wiki_page_id).with_for_update())
    if incident_page is None or incident_page.deleted_at is not None:
        raise IncidentRelationshipConflictError("The linked incident Wiki page is missing or deleted")

    result = IncidentRelationshipBuildResult(incident_id=incident.id, wiki_page_id=incident_page.id)
    generated_specs: list[dict[str, object]] = []
    if incident.system_name:
        normalized_system = normalize_text(incident.system_name)
        digest = sha256(normalized_system.encode("utf-8")).hexdigest()[:12]
        generated_specs.append(
            {
                "slug": f"generated-system-{digest}",
                "title": incident.system_name,
                "content": f"# {incident.system_name}\n\n由故障案例关联的系统知识页。\n",
                "page_type": "system",
                "relation_type": "belongs_to",
                "description": f"故障发生于系统：{incident.system_name}",
                "allow_shared": True,
            }
        )
    if incident.cause:
        generated_specs.append(
            {
                "slug": f"incident-{incident.id}-cause",
                "title": f"{incident.title}：故障原因"[:200],
                "content": f"# {incident.title}：故障原因\n\n{incident.cause}\n",
                "page_type": "event",
                "relation_type": "caused_by",
                "description": "由故障案例中的原因字段生成",
            }
        )
    if incident.solution:
        generated_specs.append(
            {
                "slug": f"incident-{incident.id}-solution",
                "title": f"{incident.title}：解决方案"[:200],
                "content": f"# {incident.title}：解决方案\n\n{incident.solution}\n",
                "page_type": "process",
                "relation_type": "resolved_by",
                "description": "由故障案例中的解决方案字段生成",
            }
        )

    for spec in generated_specs:
        page, relationship, state = upsert_generated_page(
            db,
            incident_page=incident_page,
            user=user,
            **spec,
        )
        if state == "created":
            result.created_page_ids.append(page.id)
        elif state == "updated":
            result.updated_page_ids.append(page.id)
        result.relationship_ids.append(relationship.id)

    candidates = db.scalars(
        select(IncidentCase).where(
            IncidentCase.id != incident.id,
            IncidentCase.deleted_at.is_(None),
            IncidentCase.wiki_page_id.is_not(None),
        )
    ).all()
    for candidate in candidates:
        score = incident_similarity(incident, candidate)
        if score < similarity_threshold or candidate.wiki_page_id is None:
            continue
        candidate_page = db.scalar(
            select(WikiPage).where(WikiPage.id == candidate.wiki_page_id, WikiPage.deleted_at.is_(None))
        )
        if candidate_page is None:
            continue
        source_id, target_id = sorted((incident_page.id, candidate_page.id))
        relationship = upsert_relationship(
            db,
            source_page_id=source_id,
            target_page_id=target_id,
            relation_type="similar_to",
            description=f"故障案例确定性相似度：{score:.2f}",
            user=user,
        )
        result.relationship_ids.append(relationship.id)
        result.similar_incident_ids.append(candidate.id)

    return result
