from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.document_index_job import DocumentIndexJob
from app.models.user import User
from app.models.wiki_attachment import WikiAttachment
from app.models.wiki_page import WikiPage
from app.schemas.document_index import DocumentIndexJobResponse
from app.services.audit import record_audit_log


router = APIRouter(prefix="/api/v1/wiki", tags=["wiki-index"])


def get_page_attachment_or_404(db: Session, page_id: int, attachment_id: int) -> tuple[WikiPage, WikiAttachment]:
    page = db.scalar(select(WikiPage).where(WikiPage.id == page_id, WikiPage.deleted_at.is_(None)))
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wiki page not found",
        )

    attachment = db.scalar(
        select(WikiAttachment).where(
            WikiAttachment.id == attachment_id,
            WikiAttachment.page_id == page_id,
        )
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    return page, attachment


@router.post(
    "/pages/{page_id}/attachments/{attachment_id}/index",
    response_model=DocumentIndexJobResponse,
)
def start_attachment_index(
    page_id: int,
    attachment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> DocumentIndexJob:
    get_page_attachment_or_404(db, page_id, attachment_id)

    job = DocumentIndexJob(
        page_id=page_id,
        attachment_id=attachment_id,
        status="pending",
        chunk_count=0,
    )
    db.add(job)
    db.flush()
    record_audit_log(
        db,
        action="document.index.create",
        actor=current_user,
        request=request,
        resource_type="wiki_attachment",
        resource_id=str(attachment_id),
        detail={"page_id": page_id, "job_id": job.id},
    )
    db.commit()
    db.refresh(job)
    return job


@router.get(
    "/pages/{page_id}/attachments/{attachment_id}/index",
    response_model=DocumentIndexJobResponse,
)
def read_latest_attachment_index(
    page_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> DocumentIndexJob:
    get_page_attachment_or_404(db, page_id, attachment_id)

    job = db.scalar(
        select(DocumentIndexJob)
        .where(
            DocumentIndexJob.page_id == page_id,
            DocumentIndexJob.attachment_id == attachment_id,
        )
        .order_by(desc(DocumentIndexJob.created_at), desc(DocumentIndexJob.id))
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document index job not found",
        )
    return job
