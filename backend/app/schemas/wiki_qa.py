from pydantic import BaseModel, Field, field_validator


class WikiQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    page_ids: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("question cannot be blank")
        return normalized


class WikiCitation(BaseModel):
    page_id: int
    title: str
    slug: str


class WikiAnswerMetadata(BaseModel):
    provider: str
    model: str
    duration_ms: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class WikiAnswerResponse(BaseModel):
    answer: str
    citations: list[WikiCitation] = Field(default_factory=list)
    insufficient_knowledge: bool = False
    metadata: WikiAnswerMetadata
