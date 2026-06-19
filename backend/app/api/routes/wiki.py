import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_superuser, get_current_user, get_db, require_permission
from app.core.config import MAX_UPLOAD_BYTES, PROJECT_ROOT, UPLOAD_STORAGE_DIR
from app.models.user import User
from app.models.wiki_attachment import WikiAttachment
from app.models.wiki_category import WikiCategory
from app.models.wiki_page import WikiPage
from app.models.wiki_page_relationship import WikiPageRelationship
from app.models.wiki_page_tag import WikiPageTag
from app.models.wiki_tag import WikiTag
from app.models.wiki_version import WikiVersion
from app.schemas.wiki import (
    AttachmentResponse,
    CategoryCreate,
    CategoryResponse,
    TagCreate,
    TagResponse,
    WikiPageRelationshipCreate,
    WikiPageRelationshipResponse,
    WikiPageRelationshipUpdate,
    WikiPageCreate,
    WikiPageListItem,
    WikiPageResponse,
    WikiPageUpdate,
    WikiSearchRelationship,
    WikiSearchResult,
    WikiVersionResponse,
)
from app.services.audit import record_audit_log


router = APIRouter(prefix="/api/v1/wiki", tags=["wiki"])

SUPPORTED_ATTACHMENT_TYPES = {
    "text/markdown",
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}


def ensure_unique_slug(db: Session, model: type[WikiCategory] | type[WikiTag] | type[WikiPage], slug: str, exclude_id: int | None = None) -> None:
    query = select(model).where(model.slug == slug)
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")


def get_page_or_404(db: Session, page_id: int, include_deleted: bool = False) -> WikiPage:
    query = select(WikiPage).where(WikiPage.id == page_id)
    if not include_deleted:
        query = query.where(WikiPage.deleted_at.is_(None))
    page = db.scalar(query)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wiki page not found")
    return page


def get_relationship_or_404(db: Session, relationship_id: int) -> WikiPageRelationship:
    relationship = db.scalar(select(WikiPageRelationship).where(WikiPageRelationship.id == relationship_id))
    if relationship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wiki page relationship not found")
    return relationship


def validate_category(db: Session, category_id: int | None) -> None:
    if category_id is None:
        return
    if db.scalar(select(WikiCategory).where(WikiCategory.id == category_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


def load_tags(db: Session, tag_ids: list[int]) -> list[WikiTag]:
    if not tag_ids:
        return []
    unique_ids = sorted(set(tag_ids))
    tags = db.scalars(select(WikiTag).where(WikiTag.id.in_(unique_ids))).all()
    if len(tags) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more tags were not found")
    return list(tags)


def validate_relationship_pages(db: Session, source_page_id: int, target_page_id: int) -> None:
    if source_page_id == target_page_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A page cannot relate to itself")
    get_page_or_404(db, source_page_id)
    get_page_or_404(db, target_page_id)


def ensure_unique_relationship(
    db: Session,
    source_page_id: int,
    target_page_id: int,
    relation_type: str,
    exclude_id: int | None = None,
) -> None:
    query = select(WikiPageRelationship).where(
        WikiPageRelationship.source_page_id == source_page_id,
        WikiPageRelationship.target_page_id == target_page_id,
        WikiPageRelationship.relation_type == relation_type,
    )
    if exclude_id is not None:
        query = query.where(WikiPageRelationship.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Wiki page relationship already exists")


def replace_page_tags(db: Session, page: WikiPage, tag_ids: list[int]) -> None:
    tags = load_tags(db, tag_ids)
    page.tags.clear()
    for tag in tags:
        page.tags.append(WikiPageTag(page_id=page.id, tag_id=tag.id))


def next_version_number(db: Session, page_id: int) -> int:
    current = db.scalar(select(func.max(WikiVersion.version_number)).where(WikiVersion.page_id == page_id))
    return int(current or 0) + 1


def create_version(db: Session, page: WikiPage, user: User) -> WikiVersion:
    version = WikiVersion(
        page_id=page.id,
        title=page.title,
        content=page.content,
        version_number=next_version_number(db, page.id),
        created_by_user_id=user.id,
    )
    db.add(version)
    return version


def page_response(page: WikiPage) -> WikiPageResponse:
    return WikiPageResponse(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        status=page.status,
        category_id=page.category_id,
        author_user_id=page.author_user_id,
        created_at=page.created_at,
        updated_at=page.updated_at,
        tag_ids=[item.tag_id for item in page.tags],
    )


def build_search_summary(content: str, keyword: str, max_length: int = 160) -> str:
    compact = " ".join(content.split())
    if len(compact) <= max_length:
        return compact

    keyword_index = compact.lower().find(keyword.lower())
    if keyword_index < 0:
        return f"{compact[: max_length - 3]}..."

    start = max(keyword_index - 50, 0)
    end = min(start + max_length, len(compact))
    snippet = compact[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{snippet}{suffix}"


def search_result(
    page: WikiPage,
    keyword: str,
    relationships: list[WikiSearchRelationship] | None = None,
) -> WikiSearchResult:
    return WikiSearchResult(
        id=page.id,
        title=page.title,
        slug=page.slug,
        status=page.status,
        summary=build_search_summary(page.content, keyword),
        category_id=page.category_id,
        updated_at=page.updated_at,
        relationships=relationships or [],
    )


def load_search_relationships(
    db: Session,
    page_ids: list[int],
    per_page_limit: int = 5,
) -> dict[int, list[WikiSearchRelationship]]:
    if not page_ids:
        return {}

    relationships = db.scalars(
        select(WikiPageRelationship)
        .where(or_(WikiPageRelationship.source_page_id.in_(page_ids), WikiPageRelationship.target_page_id.in_(page_ids)))
        .order_by(desc(WikiPageRelationship.updated_at), desc(WikiPageRelationship.id))
    ).all()
    related_page_ids = {
        relationship.target_page_id if relationship.source_page_id in page_ids else relationship.source_page_id
        for relationship in relationships
    }
    related_pages = {}
    if related_page_ids:
        related_pages = {
            page.id: page.title
            for page in db.scalars(
                select(WikiPage).where(WikiPage.id.in_(related_page_ids), WikiPage.deleted_at.is_(None))
            ).all()
        }

    result: dict[int, list[WikiSearchRelationship]] = {page_id: [] for page_id in page_ids}
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
                    id=relationship.id,
                    source_page_id=relationship.source_page_id,
                    target_page_id=relationship.target_page_id,
                    relation_type=relationship.relation_type,
                    related_page_id=related_page_id,
                    related_page_title=related_pages[related_page_id],
                )
            )
    return result


def validate_attachment_upload(file: UploadFile) -> tuple[str, str]:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    content_type = file.content_type or ""
    if not filename or suffix not in SUPPORTED_EXTENSIONS or content_type not in SUPPORTED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported attachment type")
    return filename, suffix


def get_upload_size(file: UploadFile) -> int:
    file.file.seek(0, 2)
    size_bytes = file.file.tell()
    file.file.seek(0)
    if size_bytes <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment file is empty")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Attachment file is too large")
    return size_bytes


def save_attachment_file(page_id: int, file: UploadFile, suffix: str) -> str:
    page_dir = UPLOAD_STORAGE_DIR / str(page_id)
    page_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{suffix}"
    destination = page_dir / stored_filename
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    try:
        return str(destination.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(destination)


@router.post("/categories", response_model=CategoryResponse)
def create_category(
    payload: CategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:create")),
) -> WikiCategory:
    ensure_unique_slug(db, WikiCategory, payload.slug)
    if payload.parent_id is not None and db.scalar(select(WikiCategory).where(WikiCategory.id == payload.parent_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent category not found")

    category = WikiCategory(name=payload.name, slug=payload.slug, parent_id=payload.parent_id)
    db.add(category)
    db.flush()
    record_audit_log(db, action="wiki.category.create", actor=current_user, request=request, resource_type="wiki_category", resource_id=str(category.id))
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiCategory]:
    return list(db.scalars(select(WikiCategory).order_by(WikiCategory.name)).all())


@router.post("/tags", response_model=TagResponse)
def create_tag(
    payload: TagCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:create")),
) -> WikiTag:
    ensure_unique_slug(db, WikiTag, payload.slug)
    tag = WikiTag(name=payload.name, slug=payload.slug)
    db.add(tag)
    db.flush()
    record_audit_log(db, action="wiki.tag.create", actor=current_user, request=request, resource_type="wiki_tag", resource_id=str(tag.id))
    db.commit()
    db.refresh(tag)
    return tag


@router.get("/tags", response_model=list[TagResponse])
def list_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiTag]:
    return list(db.scalars(select(WikiTag).order_by(WikiTag.name)).all())


@router.post("/pages", response_model=WikiPageResponse)
def create_page(
    payload: WikiPageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:create")),
) -> WikiPageResponse:
    ensure_unique_slug(db, WikiPage, payload.slug)
    validate_category(db, payload.category_id)
    load_tags(db, payload.tag_ids)

    page = WikiPage(
        title=payload.title,
        slug=payload.slug,
        content=payload.content,
        status=payload.status,
        category_id=payload.category_id,
        author_user_id=current_user.id,
    )
    db.add(page)
    db.flush()
    replace_page_tags(db, page, payload.tag_ids)
    create_version(db, page, current_user)
    record_audit_log(db, action="wiki.page.create", actor=current_user, request=request, resource_type="wiki_page", resource_id=str(page.id))
    db.commit()
    db.refresh(page)
    return page_response(page)


@router.get("/pages", response_model=list[WikiPageListItem])
def list_pages(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiPage]:
    query = select(WikiPage).where(WikiPage.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.where(or_(WikiPage.title.ilike(like), WikiPage.content.ilike(like)))
    return list(db.scalars(query.order_by(desc(WikiPage.updated_at))).all())


@router.get("/search", response_model=list[WikiSearchResult])
def search_pages(
    q: str = Query(min_length=1, max_length=100),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|published|archived)$"),
    category_id: int | None = Query(default=None, ge=1),
    tag_id: int | None = Query(default=None, ge=1),
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiSearchResult]:
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Search keyword cannot be empty")
    if updated_from is not None and updated_to is not None and updated_from > updated_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="updated_from cannot be later than updated_to")

    like = f"%{keyword}%"
    title_match = WikiPage.title.ilike(like)
    content_match = WikiPage.content.ilike(like)
    query = select(WikiPage).where(WikiPage.deleted_at.is_(None), or_(title_match, content_match))
    if status_filter is not None:
        query = query.where(WikiPage.status == status_filter)
    if category_id is not None:
        query = query.where(WikiPage.category_id == category_id)
    if tag_id is not None:
        query = query.where(WikiPage.id.in_(select(WikiPageTag.page_id).where(WikiPageTag.tag_id == tag_id)))
    if updated_from is not None:
        query = query.where(WikiPage.updated_at >= updated_from)
    if updated_to is not None:
        query = query.where(WikiPage.updated_at <= updated_to)

    pages = list(db.scalars(query.order_by(desc(title_match), desc(WikiPage.updated_at)).limit(limit)).all())
    relationship_map = load_search_relationships(db, [page.id for page in pages])
    return [search_result(page, keyword, relationship_map.get(page.id, [])) for page in pages]


@router.get("/pages/{page_id}", response_model=WikiPageResponse)
def read_page(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> WikiPageResponse:
    page = get_page_or_404(db, page_id)
    return page_response(page)


@router.put("/pages/{page_id}", response_model=WikiPageResponse)
def update_page(
    page_id: int,
    payload: WikiPageUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> WikiPageResponse:
    page = get_page_or_404(db, page_id)
    if payload.slug is not None:
        ensure_unique_slug(db, WikiPage, payload.slug, exclude_id=page.id)
        page.slug = payload.slug
    if payload.category_id is not None:
        validate_category(db, payload.category_id)
        page.category_id = payload.category_id
    if payload.title is not None:
        page.title = payload.title
    if payload.content is not None:
        page.content = payload.content
    if payload.status is not None:
        page.status = payload.status
    if payload.tag_ids is not None:
        replace_page_tags(db, page, payload.tag_ids)

    create_version(db, page, current_user)
    record_audit_log(db, action="wiki.page.update", actor=current_user, request=request, resource_type="wiki_page", resource_id=str(page.id))
    db.commit()
    db.refresh(page)
    return page_response(page)


@router.delete("/pages/{page_id}")
def delete_page(
    page_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> dict[str, str]:
    page = get_page_or_404(db, page_id)
    page.deleted_at = datetime.now(timezone.utc)
    record_audit_log(db, action="wiki.page.delete", actor=current_user, request=request, resource_type="wiki_page", resource_id=str(page.id))
    db.commit()
    return {"status": "ok"}


@router.get("/pages/{page_id}/versions", response_model=list[WikiVersionResponse])
def list_versions(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiVersion]:
    get_page_or_404(db, page_id)
    return list(db.scalars(select(WikiVersion).where(WikiVersion.page_id == page_id).order_by(desc(WikiVersion.version_number))).all())


@router.post("/pages/{page_id}/relationships", response_model=WikiPageRelationshipResponse)
def create_page_relationship(
    page_id: int,
    payload: WikiPageRelationshipCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> WikiPageRelationship:
    validate_relationship_pages(db, page_id, payload.target_page_id)
    ensure_unique_relationship(db, page_id, payload.target_page_id, payload.relation_type)

    relationship = WikiPageRelationship(
        source_page_id=page_id,
        target_page_id=payload.target_page_id,
        relation_type=payload.relation_type,
        description=payload.description,
        source_type="manual",
        created_by_user_id=current_user.id,
    )
    db.add(relationship)
    db.flush()
    record_audit_log(
        db,
        action="wiki.relationship.create",
        actor=current_user,
        request=request,
        resource_type="wiki_page_relationship",
        resource_id=str(relationship.id),
        detail={
            "source_page_id": relationship.source_page_id,
            "target_page_id": relationship.target_page_id,
            "relation_type": relationship.relation_type,
        },
    )
    db.commit()
    db.refresh(relationship)
    return relationship


@router.get("/pages/{page_id}/relationships", response_model=list[WikiPageRelationshipResponse])
def list_page_relationships(
    page_id: int,
    direction: str = Query(default="outgoing", pattern="^(outgoing|incoming|both)$"),
    relation_type: str | None = Query(default=None, pattern="^(references|depends_on|belongs_to|related_to|similar_to|caused_by|resolved_by)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiPageRelationship]:
    get_page_or_404(db, page_id)
    query = select(WikiPageRelationship)
    if direction == "outgoing":
        query = query.where(WikiPageRelationship.source_page_id == page_id)
    elif direction == "incoming":
        query = query.where(WikiPageRelationship.target_page_id == page_id)
    else:
        query = query.where(or_(WikiPageRelationship.source_page_id == page_id, WikiPageRelationship.target_page_id == page_id))
    if relation_type is not None:
        query = query.where(WikiPageRelationship.relation_type == relation_type)
    return list(db.scalars(query.order_by(desc(WikiPageRelationship.updated_at), desc(WikiPageRelationship.id))).all())


@router.put("/relationships/{relationship_id}", response_model=WikiPageRelationshipResponse)
def update_page_relationship(
    relationship_id: int,
    payload: WikiPageRelationshipUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> WikiPageRelationship:
    relationship = get_relationship_or_404(db, relationship_id)
    target_page_id = payload.target_page_id if payload.target_page_id is not None else relationship.target_page_id
    relation_type = payload.relation_type if payload.relation_type is not None else relationship.relation_type

    validate_relationship_pages(db, relationship.source_page_id, target_page_id)
    ensure_unique_relationship(db, relationship.source_page_id, target_page_id, relation_type, exclude_id=relationship.id)

    relationship.target_page_id = target_page_id
    relationship.relation_type = relation_type
    if "description" in payload.model_fields_set:
        relationship.description = payload.description

    record_audit_log(
        db,
        action="wiki.relationship.update",
        actor=current_user,
        request=request,
        resource_type="wiki_page_relationship",
        resource_id=str(relationship.id),
        detail={
            "source_page_id": relationship.source_page_id,
            "target_page_id": relationship.target_page_id,
            "relation_type": relationship.relation_type,
        },
    )
    db.commit()
    db.refresh(relationship)
    return relationship


@router.delete("/relationships/{relationship_id}")
def delete_page_relationship(
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> dict[str, str]:
    relationship = get_relationship_or_404(db, relationship_id)
    record_audit_log(
        db,
        action="wiki.relationship.delete",
        actor=current_user,
        request=request,
        resource_type="wiki_page_relationship",
        resource_id=str(relationship.id),
        detail={
            "source_page_id": relationship.source_page_id,
            "target_page_id": relationship.target_page_id,
            "relation_type": relationship.relation_type,
        },
    )
    db.delete(relationship)
    db.commit()
    return {"status": "ok"}


@router.post("/pages/{page_id}/attachments", response_model=AttachmentResponse)
def create_attachment(
    page_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:update")),
) -> WikiAttachment:
    get_page_or_404(db, page_id)
    filename, suffix = validate_attachment_upload(file)
    size_bytes = get_upload_size(file)
    storage_path = save_attachment_file(page_id, file, suffix)
    attachment = WikiAttachment(
        page_id=page_id,
        filename=filename,
        content_type=file.content_type or "",
        size_bytes=size_bytes,
        storage_path=storage_path,
        uploaded_by_user_id=current_user.id,
    )
    db.add(attachment)
    db.flush()
    record_audit_log(db, action="wiki.attachment.create", actor=current_user, request=request, resource_type="wiki_attachment", resource_id=str(attachment.id))
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/pages/{page_id}/attachments", response_model=list[AttachmentResponse])
def list_attachments(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:read")),
) -> list[WikiAttachment]:
    get_page_or_404(db, page_id)
    return list(db.scalars(select(WikiAttachment).where(WikiAttachment.page_id == page_id).order_by(desc(WikiAttachment.created_at))).all())
