from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session


@dataclass(slots=True)
class ToolContext:
    db: Session
    actor_user_id: int | None = None


class KnowledgeTool(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]

    def invoke(self, context: ToolContext, arguments: BaseModel) -> BaseModel: ...

    def summarize_result(self, result: BaseModel) -> dict[str, Any]: ...


class ToolInvocationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ToolNotFoundError(ToolInvocationError):
    def __init__(self, tool_name: str) -> None:
        super().__init__("tool_not_found", f"Tool is not registered: {tool_name}")
