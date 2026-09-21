from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.category import CategoryOut
from schemas.technology import TechnologyOut
from schemas.user import UserOut
from utils.validation import validate_slug


class PublicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=500_000)
    source_type: Literal["article", "task", "case", "changelog"] = "article"
    source_uid: Optional[UUID] = None
    extra_data: Optional[dict] = Field(default_factory=dict)
    category_id: Optional[UUID] = None
    author_id: UUID
    is_published: bool = False
    technology_ids: Optional[List[UUID]] = None

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("category_id", "source_uid", mode="before")
    @classmethod
    def empty_uuid_to_none(cls, value):
        if value == "":
            return None
        return value


class PublicationUpdate(PublicationCreate):
    pass


class PublicationOut(BaseModel):
    id: UUID
    title: str
    content: str
    slug: str
    source_type: str = "article"
    source_uid: Optional[UUID] = None
    extra_data: Optional[dict] = Field(default_factory=dict)
    category_id: Optional[UUID] = None
    author_id: Optional[UUID] = None
    is_published: bool = False
    technology_ids: Optional[List[UUID]] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    author: Optional[UserOut] = None
    category: Optional[CategoryOut] = None
    technologies: List[TechnologyOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
