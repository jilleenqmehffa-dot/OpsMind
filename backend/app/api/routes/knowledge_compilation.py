from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.knowledge_compilation_job import KnowledgeCompilationJob
from app.models.knowledge_unit import KnowledgeUnit
from app.models.user import User
from app.models.wiki_attachment import WikiAttachment
from app.models.wiki_page import WikiPage
from app.schemas.knowledge_compilation import (
    KnowledgeCompilationJobResponse,
    KnowledgeUnitApplyRequest,
    KnowledgeUnitResponse,
)
from app.services.knowledge_extractor import extract_knowledge_units
from app.services.source_parser import SourceParseError, parse_source_document
from app.services.audit import record_audit_log


router = APIRouter(prefix="/api/v1/wiki", tags=["knowledge-compilation"])


def get_attachment_or_404(db: Session, attachment_id: int) -> WikiAttachment:
    attachment = db.scalar(select(WikiAttachment).where(WikiAttachment.id == attachment_id))
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return attachment


def get_page_or_404(db: Session, page_id: int) -> WikiPage:
    page = db.scalar(select(WikiPage).where(WikiPage.id == page_id, WikiPage.deleted_at.is_(None)))
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wiki page not found",
        )
    return page


def get_unit_or_404(db: Session, unit_id: int) -> KnowledgeUnit:
    unit = db.scalar(select(KnowledgeUnit).where(KnowledgeUnit.id == unit_id))
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge unit not found",
        )
    return unit


@router.post(
    "/attachments/{attachment_id}/compile",
    response_model=KnowledgeCompilationJobResponse,
)
def create_compilation_job(
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> KnowledgeCompilationJob:
    attachment = get_attachment_or_404(db, attachment_id)

    job = KnowledgeCompilationJob(
        page_id=attachment.page_id,
        attachment_id=attachment.id,
        status="parsing",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()

    try:
        document = parse_source_document(
            attachment_id=attachment.id,
            filename=attachment.filename,
            storage_path=attachment.storage_path,
            content_type=attachment.content_type,
        )
        job.status = "extracting"
        candidates = extract_knowledge_units(document)
        for candidate in candidates:
            db.add(
                KnowledgeUnit(
                    job_id=job.id,
                    source_attachment_id=attachment.id,
                    source_page_id=attachment.page_id,
                    title=candidate.title,
                    unit_type=candidate.unit_type,
                    summary=candidate.summary,
                    content=candidate.content,
                    source_location=candidate.source_location,
                    confidence=candidate.confidence,
                    merge_hint_title=candidate.merge_hint_title,
                    apply_status="pending",
                )
            )

        job.status = "ready"
        job.knowledge_unit_count = len(candidates)
        job.finished_at = datetime.now(timezone.utc)
    except SourceParseError as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Knowledge extraction failed: {exc}"
        job.finished_at = datetime.now(timezone.utc)

    record_audit_log(
        db,
        action="knowledge.compilation.create",
        actor=current_user,
        request=request,
        resource_type="wiki_attachment",
        resource_id=str(attachment.id),
        detail={"page_id": attachment.page_id, "job_id": job.id, "status": job.status},
    )
    db.commit()
    db.refresh(job)
    return job


@router.get(
    "/attachments/{attachment_id}/compile",
    response_model=KnowledgeCompilationJobResponse,
)
def read_latest_compilation_job(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> KnowledgeCompilationJob:
    get_attachment_or_404(db, attachment_id)

    job = db.scalar(
        select(KnowledgeCompilationJob)
        .where(KnowledgeCompilationJob.attachment_id == attachment_id)
        .order_by(desc(KnowledgeCompilationJob.created_at), desc(KnowledgeCompilationJob.id))
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge compilation job not found",
        )
    return job


@router.get(
    "/pages/{page_id}/compilation-jobs",
    response_model=list[KnowledgeCompilationJobResponse],
)
def list_page_compilation_jobs(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[KnowledgeCompilationJob]:
    get_page_or_404(db, page_id)
    return list(
        db.scalars(
            select(KnowledgeCompilationJob)
            .where(KnowledgeCompilationJob.page_id == page_id)
            .order_by(desc(KnowledgeCompilationJob.created_at), desc(KnowledgeCompilationJob.id))
        ).all()
    )


@router.get(
    "/knowledge-units",
    response_model=list[KnowledgeUnitResponse],
)
def list_knowledge_units(
    job_id: int | None = None,
    attachment_id: int | None = None,
    page_id: int | None = None,
    unit_type: str | None = None,
    apply_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[KnowledgeUnit]:
    query = select(KnowledgeUnit)
    if job_id is not None:
        query = query.where(KnowledgeUnit.job_id == job_id)
    if attachment_id is not None:
        query = query.where(KnowledgeUnit.source_attachment_id == attachment_id)
    if page_id is not None:
        query = query.where(KnowledgeUnit.source_page_id == page_id)
    if unit_type is not None:
        query = query.where(KnowledgeUnit.unit_type == unit_type)
    if apply_status is not None:
        query = query.where(KnowledgeUnit.apply_status == apply_status)

    return list(db.scalars(query.order_by(desc(KnowledgeUnit.created_at), desc(KnowledgeUnit.id))).all())


@router.post(
    "/knowledge-units/{unit_id}/apply",
    response_model=KnowledgeUnitResponse,
)
def apply_knowledge_unit(
    unit_id: int,
    payload: KnowledgeUnitApplyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> KnowledgeUnit:
    unit = get_unit_or_404(db, unit_id)
    if payload.target_page_id is not None:
        get_page_or_404(db, payload.target_page_id)

    if payload.action == "apply":
        unit.apply_status = "applied"
        unit.created_page_id = payload.target_page_id
    elif payload.action == "skip":
        unit.apply_status = "skipped"
    else:
        unit.apply_status = "rejected"
    unit.review_note = payload.review_note

    record_audit_log(
        db,
        action=f"knowledge.unit.{payload.action}",
        actor=current_user,
        request=request,
        resource_type="knowledge_unit",
        resource_id=str(unit.id),
        detail={"target_page_id": payload.target_page_id},
    )
    db.commit()
    db.refresh(unit)
    return unit
