from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.knowledge_agent import (
    KnowledgeAgentMetadata,
    KnowledgeAgentRunRequest,
    KnowledgeAgentRunResponse,
    KnowledgeAgentStepResponse,
)
from app.services.knowledge_agent import KnowledgeAgentError, run_knowledge_agent
from app.services.llm_provider import get_llm_provider
from app.tools.base import ToolContext


router = APIRouter(prefix="/api/v1/knowledge-agent", tags=["knowledge-agent"])


@router.post("/runs", response_model=KnowledgeAgentRunResponse)
def create_knowledge_agent_run(
    payload: KnowledgeAgentRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeAgentRunResponse:
    try:
        provider = get_llm_provider()
        result = run_knowledge_agent(
            payload.task,
            provider=provider,
            context=ToolContext(db=db, actor_user_id=current_user.id),
            allowed_write_tools=set(payload.allowed_write_tools),
            max_steps=payload.max_steps,
            max_observation_chars=payload.max_observation_chars,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except KnowledgeAgentError as error:
        raise HTTPException(
            status_code=_status_code_for_agent_error(error.code),
            detail={"code": error.code, "message": str(error)},
        ) from error

    return KnowledgeAgentRunResponse(
        answer=result.answer,
        steps=[
            KnowledgeAgentStepResponse(
                tool_name=step.tool_name,
                status=step.status,
                error_code=step.error_code,
                observation_truncated=step.observation_truncated,
            )
            for step in result.steps
        ],
        metadata=KnowledgeAgentMetadata(
            provider=result.provider,
            model=result.model,
            duration_ms=result.duration_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        ),
    )


def _status_code_for_agent_error(code: str) -> int:
    if code in {"actor_required", "tool_not_allowed"}:
        return status.HTTP_403_FORBIDDEN
    if code in {"invalid_model_output", "provider_error", "step_limit_exceeded"}:
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_400_BAD_REQUEST
