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


class WikiVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    title: str
    content: str
    version_number: int
    created_by_user_id: int | None
    created_at: datetime


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
