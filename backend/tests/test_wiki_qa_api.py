import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.api.deps import get_current_user
from app.api.routes import wiki_qa as wiki_qa_route
from app.main import app
from app.models.user import User
from app.schemas.wiki_qa import (
    WikiAnswerMetadata,
    WikiAnswerResponse,
    WikiCitation,
    WikiQuestionRequest,
)
from app.services.wiki_qa import WikiQuestionError


def make_user() -> User:
    return User(
        id=1,
        username="reader",
        password_hash="unused",
        is_active=True,
        is_superuser=False,
    )


def test_wiki_question_route_is_registered_and_protected() -> None:
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/wiki/questions"
    )

    assert route.methods == {"POST"}
    assert route.response_model is WikiAnswerResponse
    assert any(dependency.call is get_current_user for dependency in route.dependant.dependencies)


def test_wiki_question_returns_service_response(monkeypatch) -> None:
    captured = {}
    db = object()

    def fake_answer(received_db, question, *, page_ids):
        captured.update(db=received_db, question=question, page_ids=page_ids)
        return WikiAnswerResponse(
            answer="检查复制延迟指标。[Wiki:7]",
            citations=[WikiCitation(page_id=7, title="数据库延迟", slug="database-lag")],
            insufficient_knowledge=False,
            metadata=WikiAnswerMetadata(
                provider="stub",
                model="stub-model",
                duration_ms=15,
                prompt_tokens=20,
                completion_tokens=6,
                total_tokens=26,
            ),
        )

    monkeypatch.setattr(wiki_qa_route, "answer_wiki_question", fake_answer)
    payload = WikiQuestionRequest(
        question="  如何排查   数据库延迟？  ",
        page_ids=[7],
    )

    response = wiki_qa_route.create_wiki_answer(payload, db, make_user())

    assert response.citations[0].page_id == 7
    assert response.metadata.total_tokens == 26
    assert captured == {
        "db": db,
        "question": "如何排查 数据库延迟？",
        "page_ids": [7],
    }


def test_wiki_question_rejects_blank_question() -> None:
    with pytest.raises(ValidationError, match="question cannot be blank"):
        WikiQuestionRequest(question="   ")


def test_wiki_question_maps_service_error_to_bad_gateway(monkeypatch) -> None:
    def fail_answer(db, question, *, page_ids):
        raise WikiQuestionError("provider secret must not leak")

    monkeypatch.setattr(wiki_qa_route, "answer_wiki_question", fail_answer)

    with pytest.raises(HTTPException) as captured:
        wiki_qa_route.create_wiki_answer(
            WikiQuestionRequest(question="如何排查数据库延迟？"),
            object(),
            make_user(),
        )

    assert captured.value.status_code == 502
    assert captured.value.detail == "Wiki answer generation failed"
