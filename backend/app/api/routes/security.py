from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_superuser, get_current_user, get_db, require_permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import record_audit_log


router = APIRouter(prefix="/api/v1/security", tags=["security"])


@router.get("/protected")
def read_protected(current_user: User = Depends(get_current_user)) -> dict[str, object]:
    return {
        "status": "ok",
        "username": current_user.username,
        "is_superuser": current_user.is_superuser,
    }


@router.post("/wiki/create-check")
def check_wiki_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("wiki:create")),
) -> dict[str, str]:
    record_audit_log(
        db,
        action="wiki.create",
        actor=current_user,
        request=request,
        resource_type="wiki",
        result="success",
        detail={"source": "m1_permission_check"},
    )
    db.commit()
    return {"status": "ok", "message": "wiki create permission granted"}


@router.delete("/wiki/delete-check/{resource_id}")
def check_wiki_delete(
    resource_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> dict[str, str]:
    record_audit_log(
        db,
        action="wiki.delete",
        actor=current_user,
        request=request,
        resource_type="wiki",
        resource_id=resource_id,
        result="success",
        detail={"source": "m1_permission_check"},
    )
    db.commit()
    return {"status": "ok", "message": "wiki delete permission granted"}


@router.get("/audit-logs")
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> list[dict[str, object | None]]:
    logs = db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(20)).all()
    return [
        {
            "id": item.id,
            "actor_user_id": item.actor_user_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "result": item.result,
            "detail": item.detail,
            "created_at": item.created_at.isoformat(),
        }
        for item in logs
    ]
