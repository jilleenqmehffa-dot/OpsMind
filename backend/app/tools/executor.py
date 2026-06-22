from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from app.models.tool_invocation import ToolInvocation
from app.tools.base import ToolContext, ToolInvocationError
from app.tools.registry import ToolRegistry


SENSITIVE_KEYS = {"api_key", "authorization", "password", "secret", "token"}


def sanitize_summary(value: Any, *, max_string_length: int = 200) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(sensitive_key in str(key).lower() for sensitive_key in SENSITIVE_KEYS)
                else sanitize_summary(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_summary(item) for item in value[:50]]
    if isinstance(value, str):
        return value if len(value) <= max_string_length else f"{value[:max_string_length]}..."
    return value


def persist_failure(
    context: ToolContext,
    *,
    tool_name: str,
    input_summary: dict[str, Any],
    error_code: str,
    duration_ms: int,
) -> None:
    context.db.rollback()
    context.db.add(
        ToolInvocation(
            tool_name=tool_name,
            actor_user_id=context.actor_user_id,
            status="failed",
            error_code=error_code,
            input_summary=input_summary,
            result_summary=None,
            duration_ms=duration_ms,
        )
    )
    context.db.commit()


def execute_tool(
    registry: ToolRegistry,
    tool_name: str,
    arguments: dict[str, Any],
    context: ToolContext,
) -> BaseModel:
    started_at = perf_counter()
    input_summary = sanitize_summary(arguments)
    try:
        tool = registry.get(tool_name)
    except ToolInvocationError as exc:
        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        persist_failure(
            context,
            tool_name=tool_name,
            input_summary=input_summary,
            error_code=exc.code,
            duration_ms=duration_ms,
        )
        raise

    try:
        parsed_arguments = tool.input_model.model_validate(arguments)
        result = tool.invoke(context, parsed_arguments)
        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        context.db.add(
            ToolInvocation(
                tool_name=tool.name,
                actor_user_id=context.actor_user_id,
                status="success",
                error_code=None,
                input_summary=input_summary,
                result_summary=sanitize_summary(tool.summarize_result(result)),
                duration_ms=duration_ms,
            )
        )
        context.db.commit()
        return result
    except ValidationError as exc:
        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        persist_failure(
            context,
            tool_name=tool.name,
            input_summary=input_summary,
            error_code="invalid_arguments",
            duration_ms=duration_ms,
        )
        raise ToolInvocationError("invalid_arguments", "Tool arguments are invalid") from exc
    except ToolInvocationError as exc:
        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        persist_failure(
            context,
            tool_name=tool.name,
            input_summary=input_summary,
            error_code=exc.code,
            duration_ms=duration_ms,
        )
        raise
    except Exception as exc:
        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        persist_failure(
            context,
            tool_name=tool.name,
            input_summary=input_summary,
            error_code="internal_error",
            duration_ms=duration_ms,
        )
        raise ToolInvocationError("internal_error", "Tool execution failed") from exc
