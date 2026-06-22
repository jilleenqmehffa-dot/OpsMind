from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.models  # noqa: F401 - registers mapped tables
from app.api.routes import incident_cases as incident_route
from app.db.base import Base
from app.main import app
from app.models.incident_case import IncidentCase
from app.models.user import User
from app.schemas.incident_case import IncidentCaseCreate, IncidentCaseResponse, IncidentCaseUpdate


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["incident_cases"]])
    return Session(engine)


def make_user() -> User:
    return User(
        id=7,
        username="operator",
        password_hash="unused",
        is_active=True,
        is_superuser=False,
    )


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/incidents",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def permission_code(dependency: object) -> str | None:
    closure = getattr(dependency, "__closure__", None) or ()
    return next(
        (
            cell.cell_contents
            for cell in closure
            if isinstance(cell.cell_contents, str) and cell.cell_contents.startswith(("incident:", "wiki:"))
        ),
        None,
    )


def test_incident_routes_are_registered_with_expected_permissions() -> None:
    routes = {
        (route.path, next(iter(route.methods))): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/incidents")
    }

    expected = {
        ("/api/v1/incidents", "POST"): "incident:create",
        ("/api/v1/incidents", "GET"): "incident:read",
        ("/api/v1/incidents/{incident_id}", "GET"): "incident:read",
        ("/api/v1/incidents/{incident_id}/publish-to-wiki", "POST"): "incident:update",
        ("/api/v1/incidents/{incident_id}/build-wiki-relationships", "POST"): "incident:update",
        ("/api/v1/incidents/{incident_id}", "PUT"): "incident:update",
        ("/api/v1/incidents/{incident_id}", "DELETE"): "incident:delete",
    }
    assert set(routes) == set(expected)
    for key, code in expected.items():
        assert code in {permission_code(item.call) for item in routes[key].dependant.dependencies}

    assert routes[("/api/v1/incidents", "POST")].response_model is IncidentCaseResponse
    publish_route = routes[("/api/v1/incidents/{incident_id}/publish-to-wiki", "POST")]
    assert {
        permission_code(item.call)
        for item in publish_route.dependant.dependencies
        if permission_code(item.call) is not None
    } == {"incident:update", "wiki:create", "wiki:update"}
    relationship_route = routes[("/api/v1/incidents/{incident_id}/build-wiki-relationships", "POST")]
    assert {
        permission_code(item.call)
        for item in relationship_route.dependant.dependencies
        if permission_code(item.call) is not None
    } == {"incident:update", "wiki:create", "wiki:update"}


def test_incident_crud_uses_soft_delete_and_records_audit(monkeypatch) -> None:
    audit_actions: list[tuple[str, str | None]] = []

    def fake_record_audit_log(db, *, action, request, resource_id=None, **kwargs):
        audit_actions.append((action, resource_id))

    monkeypatch.setattr(incident_route, "record_audit_log", fake_record_audit_log)
    occurred_at = datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc)

    with make_session() as db:
        incident = incident_route.create_incident(
            IncidentCaseCreate(
                title="Redis 连接耗尽",
                system_name="cache",
                severity="high",
                symptom="应用无法获取连接",
                occurred_at=occurred_at,
            ),
            make_request(),
            db,
            make_user(),
        )
        incident_id = incident.id

        assert incident.created_by_user_id == 7
        assert incident.updated_by_user_id == 7
        assert incident_route.read_incident(incident_id, db, make_user()).title == "Redis 连接耗尽"

        items = incident_route.list_incidents(
            q="连接",
            system_name="cache",
            severity="high",
            status_filter="open",
            occurred_from=occurred_at - timedelta(minutes=1),
            occurred_to=occurred_at + timedelta(minutes=1),
            offset=0,
            limit=10,
            db=db,
            current_user=make_user(),
        )
        assert [item.id for item in items] == [incident_id]

        updated = incident_route.update_incident(
            incident_id,
            IncidentCaseUpdate(status="resolved", solution="扩容连接池", resolved_at=occurred_at + timedelta(hours=1)),
            make_request(),
            db,
            make_user(),
        )
        assert updated.status == "resolved"
        assert updated.solution == "扩容连接池"

        assert incident_route.delete_incident(incident_id, make_request(), db, make_user()) == {"status": "ok"}
        assert db.get(IncidentCase, incident_id).deleted_at is not None
        with pytest.raises(HTTPException) as captured:
            incident_route.read_incident(incident_id, db, make_user())
        assert captured.value.status_code == 404

    assert [item[0] for item in audit_actions] == [
        "incident.case.create",
        "incident.case.update",
        "incident.case.delete",
    ]
    assert {item[1] for item in audit_actions} == {str(incident_id)}


def test_incident_rejects_invalid_time_ranges() -> None:
    occurred_at = datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)

    with pytest.raises(HTTPException, match="resolved_at cannot be earlier") as captured:
        incident_route.validate_incident_timeline(occurred_at, occurred_at - timedelta(minutes=1))
    assert captured.value.status_code == 422

    with make_session() as db, pytest.raises(HTTPException, match="occurred_from cannot be later") as captured:
        incident_route.list_incidents(
            q=None,
            system_name=None,
            severity=None,
            status_filter=None,
            occurred_from=occurred_at,
            occurred_to=occurred_at - timedelta(minutes=1),
            offset=0,
            limit=10,
            db=db,
            current_user=make_user(),
        )
    assert captured.value.status_code == 422
