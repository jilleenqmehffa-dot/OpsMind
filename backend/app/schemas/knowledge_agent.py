from typing import Literal

from pydantic import BaseModel, Field, field_validator


WritableAgentTool = Literal["wiki_page_update", "page_relationship"]


class KnowledgeAgentRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    allowed_write_tools: list[WritableAgentTool] = Field(default_factory=list, max_length=2)
    max_steps: int = Field(default=5, ge=1, le=10)
    max_observation_chars: int = Field(default=12000, ge=1000, le=50000)

    @field_validator("task")
    @classmethod
    def normalize_task(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("task cannot be blank")
        return normalized

    @field_validator("allowed_write_tools")
    @classmethod
    def reject_duplicate_write_tools(cls, value: list[WritableAgentTool]) -> list[WritableAgentTool]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_write_tools cannot contain duplicates")
        return value


class KnowledgeAgentStepResponse(BaseModel):
    tool_name: str
    status: Literal["success", "failed"]
    error_code: str | None = None
    observation_truncated: bool = False


class KnowledgeAgentMetadata(BaseModel):
    provider: str
    model: str
    duration_ms: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class KnowledgeAgentRunResponse(BaseModel):
    answer: str
    steps: list[KnowledgeAgentStepResponse] = Field(default_factory=list)
    metadata: KnowledgeAgentMetadata
