from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def record_audit_log(
    db: Session,
    *,
    action: str,
    request: Request,
    actor: User | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    result: str = "success",
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    audit_log = AuditLog(
        actor_user_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=client_host,
        user_agent=user_agent,
        result=result,
        detail=detail,
    )
    db.add(audit_log)
    return audit_log
