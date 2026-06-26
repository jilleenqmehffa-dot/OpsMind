import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.api.deps import get_current_user
from app.api.routes import knowledge_agent as knowledge_agent_route
from app.main import app
from app.models.user import User
from app.schemas.knowledge_agent import KnowledgeAgentRunRequest, KnowledgeAgentRunResponse
from app.services.knowledge_agent import AgentStep, KnowledgeAgentError, KnowledgeAgentResult


def make_user() -> User:
    return User(
        id=9,
        username="agent-user",
        password_hash="unused",
        is_active=True,
        is_superuser=True,
    )


def make_result() -> KnowledgeAgentResult:
    return KnowledgeAgentResult(
        answer="已找到 Redis 恢复流程。",
        steps=[
            AgentStep(
                tool_name="wiki_search",
                status="success",
                observation_truncated=True,
            )
        ],
        provider="stub",
        model="stub-agent",
        duration_ms=12,
        prompt_tokens=20,
        completion_tokens=8,
        total_tokens=28,
    )


def test_knowledge_agent_route_is_registered_and_protected() -> None:
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/knowledge-agent/runs"
    )

    assert route.methods == {"POST"}
    assert route.response_model is KnowledgeAgentRunResponse
    assert any(dependency.call is get_current_user for dependency in route.dependant.dependencies)


def test_knowledge_agent_route_passes_authenticated_actor_and_limits(monkeypatch) -> None:
    captured = {}
    db = object()
    provider = object()

    def fake_get_provider():
        return provider

    def fake_run(task, *, provider, context, allowed_write_tools, max_steps, max_observation_chars):
        captured.update(
            task=task,
            provider=provider,
            actor_user_id=context.actor_user_id,
            db=context.db,
            allowed_write_tools=allowed_write_tools,
            max_steps=max_steps,
            max_observation_chars=max_observation_chars,
        )
        return make_result()

    monkeypatch.setattr(knowledge_agent_route, "get_llm_provider", fake_get_provider)
    monkeypatch.setattr(knowledge_agent_route, "run_knowledge_agent", fake_run)

    response = knowledge_agent_route.create_knowledge_agent_run(
        KnowledgeAgentRunRequest(
            task="  搜索   Redis 恢复流程  ",
            allowed_write_tools=["wiki_page_update"],
            max_steps=3,
            max_observation_chars=2000,
        ),
        db,
        make_user(),
    )

    assert response.answer == "已找到 Redis 恢复流程。"
    assert response.steps[0].tool_name == "wiki_search"
    assert response.steps[0].observation_truncated is True
    assert response.metadata.total_tokens == 28
    assert captured == {
        "task": "搜索 Redis 恢复流程",
        "provider": provider,
        "actor_user_id": 9,
        "db": db,
        "allowed_write_tools": {"wiki_page_update"},
        "max_steps": 3,
        "max_observation_chars": 2000,
    }


def test_knowledge_agent_request_rejects_blank_task_and_duplicate_write_tools() -> None:
    with pytest.raises(ValidationError, match="task cannot be blank"):
        KnowledgeAgentRunRequest(task="   ")

    with pytest.raises(ValidationError, match="allowed_write_tools cannot contain duplicates"):
        KnowledgeAgentRunRequest(
            task="更新页面",
            allowed_write_tools=["wiki_page_update", "wiki_page_update"],
        )


def test_knowledge_agent_maps_errors_to_http_status(monkeypatch) -> None:
    def fake_get_provider():
        return object()

    monkeypatch.setattr(knowledge_agent_route, "get_llm_provider", fake_get_provider)

    def fail_with(code: str):
        def fake_run(*args, **kwargs):
            raise KnowledgeAgentError(code, "agent error")

        monkeypatch.setattr(knowledge_agent_route, "run_knowledge_agent", fake_run)
        with pytest.raises(HTTPException) as captured:
            knowledge_agent_route.create_knowledge_agent_run(
                KnowledgeAgentRunRequest(task="搜索 Redis"),
                object(),
                make_user(),
            )
        return captured.value

    denied = fail_with("tool_not_allowed")
    assert denied.status_code == 403
    assert denied.detail == {"code": "tool_not_allowed", "message": "agent error"}

    provider_failed = fail_with("provider_error")
    assert provider_failed.status_code == 502
    assert provider_failed.detail["code"] == "provider_error"

    repeated = fail_with("repeated_tool_call")
    assert repeated.status_code == 400
    assert repeated.detail["code"] == "repeated_tool_call"
