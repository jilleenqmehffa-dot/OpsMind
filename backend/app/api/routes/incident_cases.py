from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.incident_case import IncidentCase
from app.models.user import User
from app.schemas.incident_case import (
    IncidentCaseCreate,
    IncidentCaseListItem,
    IncidentCaseResponse,
    IncidentCaseUpdate,
    IncidentRelationshipBuildResponse,
)
from app.schemas.wiki import WikiPageResponse
from app.services.audit import record_audit_log
from app.services.incident_wiki import IncidentWikiConflictError, publish_incident_to_wiki
from app.services.incident_relationships import IncidentRelationshipConflictError, build_incident_relationships


router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def get_incident_or_404(db: Session, incident_id: int) -> IncidentCase:
    incident = db.scalar(
        select(IncidentCase).where(
            IncidentCase.id == incident_id,
            IncidentCase.deleted_at.is_(None),
        )
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident case not found")
    return incident


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_incident_timeline(occurred_at: datetime | None, resolved_at: datetime | None) -> None:
    if (
        occurred_at is not None
        and resolved_at is not None
        and normalize_utc(resolved_at) < normalize_utc(occurred_at)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="resolved_at cannot be earlier than occurred_at",
        )


@router.post("", response_model=IncidentCaseResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:create")),
) -> IncidentCase:
    validate_incident_timeline(payload.occurred_at, payload.resolved_at)
    incident = IncidentCase(
        **payload.model_dump(),
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(incident)
    db.flush()
    record_audit_log(
        db,
        action="incident.case.create",
        actor=current_user,
        request=request,
        resource_type="incident_case",
        resource_id=str(incident.id),
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentCaseListItem])
def list_incidents(
    q: str | None = Query(default=None, max_length=100),
    system_name: str | None = Query(default=None, max_length=200),
    severity: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|investigating|resolved|closed)$"),
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:read")),
) -> list[IncidentCase]:
    if occurred_from is not None and occurred_to is not None and occurred_from > occurred_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="occurred_from cannot be later than occurred_to",
        )

    query = select(IncidentCase).where(IncidentCase.deleted_at.is_(None))
    if q is not None:
        keyword = q.strip()
        if not keyword:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Search keyword cannot be empty")
        like = f"%{keyword}%"
        query = query.where(
            or_(
                IncidentCase.title.ilike(like),
                IncidentCase.symptom.ilike(like),
                IncidentCase.cause.ilike(like),
                IncidentCase.solution.ilike(like),
            )
        )
    if system_name is not None:
        query = query.where(IncidentCase.system_name == system_name.strip())
    if severity is not None:
        query = query.where(IncidentCase.severity == severity)
    if status_filter is not None:
        query = query.where(IncidentCase.status == status_filter)
    if occurred_from is not None:
        query = query.where(IncidentCase.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(IncidentCase.occurred_at <= occurred_to)

    return list(
        db.scalars(
            query.order_by(desc(IncidentCase.occurred_at), desc(IncidentCase.created_at), desc(IncidentCase.id))
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.get("/{incident_id}", response_model=IncidentCaseResponse)
def read_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:read")),
) -> IncidentCase:
    return get_incident_or_404(db, incident_id)


@router.post(
    "/{incident_id}/publish-to-wiki",
    response_model=WikiPageResponse,
    dependencies=[
        Depends(require_permission("wiki:create")),
        Depends(require_permission("wiki:update")),
    ],
)
def publish_incident(
    incident_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:update")),
) -> WikiPageResponse:
    incident = db.scalar(
        select(IncidentCase)
        .where(IncidentCase.id == incident_id, IncidentCase.deleted_at.is_(None))
        .with_for_update()
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident case not found")

    try:
        page, publish_action = publish_incident_to_wiki(db, incident, current_user)
    except IncidentWikiConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.flush()
    record_audit_log(
        db,
        action="incident.case.publish_to_wiki",
        actor=current_user,
        request=request,
        resource_type="incident_case",
        resource_id=str(incident.id),
        detail={"wiki_page_id": page.id, "publish_action": publish_action},
    )
    db.commit()
    db.refresh(page)
    return WikiPageResponse(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        page_type=page.page_type,
        status=page.status,
        category_id=page.category_id,
        author_user_id=page.author_user_id,
        created_at=page.created_at,
        updated_at=page.updated_at,
        tag_ids=[item.tag_id for item in page.tags],
    )


@router.post(
    "/{incident_id}/build-wiki-relationships",
    response_model=IncidentRelationshipBuildResponse,
    dependencies=[
        Depends(require_permission("wiki:create")),
        Depends(require_permission("wiki:update")),
    ],
)
def build_incident_wiki_relationships(
    incident_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:update")),
) -> IncidentRelationshipBuildResponse:
    incident = db.scalar(
        select(IncidentCase)
        .where(IncidentCase.id == incident_id, IncidentCase.deleted_at.is_(None))
        .with_for_update()
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident case not found")

    try:
        result = build_incident_relationships(db, incident, current_user)
    except IncidentRelationshipConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.flush()
    record_audit_log(
        db,
        action="incident.case.build_wiki_relationships",
        actor=current_user,
        request=request,
        resource_type="incident_case",
        resource_id=str(incident.id),
        detail={
            "wiki_page_id": result.wiki_page_id,
            "created_page_count": len(result.created_page_ids),
            "updated_page_count": len(result.updated_page_ids),
            "relationship_count": len(result.relationship_ids),
            "similar_incident_count": len(result.similar_incident_ids),
        },
    )
    db.commit()
    return IncidentRelationshipBuildResponse(
        incident_id=result.incident_id,
        wiki_page_id=result.wiki_page_id,
        created_page_ids=result.created_page_ids,
        updated_page_ids=result.updated_page_ids,
        relationship_ids=result.relationship_ids,
        similar_incident_ids=result.similar_incident_ids,
    )


@router.put("/{incident_id}", response_model=IncidentCaseResponse)
def update_incident(
    incident_id: int,
    payload: IncidentCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:update")),
) -> IncidentCase:
    incident = get_incident_or_404(db, incident_id)
    changes = payload.model_dump(exclude_unset=True)
    occurred_at = changes.get("occurred_at", incident.occurred_at)
    resolved_at = changes.get("resolved_at", incident.resolved_at)
    validate_incident_timeline(occurred_at, resolved_at)

    for field, value in changes.items():
        setattr(incident, field, value)
    incident.updated_by_user_id = current_user.id

    record_audit_log(
        db,
        action="incident.case.update",
        actor=current_user,
        request=request,
        resource_type="incident_case",
        resource_id=str(incident.id),
        detail={"updated_fields": sorted(changes)},
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.delete("/{incident_id}")
def delete_incident(
    incident_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("incident:delete")),
) -> dict[str, str]:
    incident = get_incident_or_404(db, incident_id)
    incident.deleted_at = datetime.now(timezone.utc)
    incident.updated_by_user_id = current_user.id
    record_audit_log(
        db,
        action="incident.case.delete",
        actor=current_user,
        request=request,
        resource_type="incident_case",
        resource_id=str(incident.id),
    )
    db.commit()
    return {"status": "ok"}
