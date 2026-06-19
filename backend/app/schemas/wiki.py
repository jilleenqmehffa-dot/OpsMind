from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    parent_id: int | None
    created_at: datetime


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=120)


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime


class WikiPageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220)
    content: str = Field(min_length=1)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")
    category_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)


class WikiPageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=220)
    content: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")
    category_id: int | None = None
    tag_ids: list[int] | None = None


class WikiPageListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    status: str
    category_id: int | None
    author_user_id: int | None
    created_at: datetime
    updated_at: datetime


class WikiPageResponse(WikiPageListItem):
    content: str
    tag_ids: list[int]


class WikiSearchRelationship(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_page_id: int
    target_page_id: int
    relation_type: str
    related_page_id: int
    related_page_title: str


class WikiSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    status: str
    summary: str
    category_id: int | None
    updated_at: datetime
    relationships: list[WikiSearchRelationship] = Field(default_factory=list)


class WikiVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    title: str
    content: str
    version_number: int
    created_by_user_id: int | None
    created_at: datetime


RELATION_TYPE_PATTERN = "^(references|depends_on|belongs_to|related_to|similar_to|caused_by|resolved_by)$"


class WikiPageRelationshipCreate(BaseModel):
    target_page_id: int
    relation_type: str = Field(pattern=RELATION_TYPE_PATTERN)
    description: str | None = Field(default=None, max_length=1000)


class WikiPageRelationshipUpdate(BaseModel):
    target_page_id: int | None = None
    relation_type: str | None = Field(default=None, pattern=RELATION_TYPE_PATTERN)
    description: str | None = Field(default=None, max_length=1000)


class WikiPageRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_page_id: int
    target_page_id: int
    relation_type: str
    description: str | None
    source_type: str
    source_job_id: int | None
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class AttachmentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1, le=20 * 1024 * 1024)
    storage_path: str = Field(min_length=1, max_length=500)


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    uploaded_by_user_id: int | None
    created_at: datetime
