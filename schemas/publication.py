from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.user import UserOut


class PublicationCreate(BaseModel):
    title: str
    slug: str
    content: str
    source_type: str = "article"
    source_uid: Optional[UUID] = None
    extra_data: Optional[dict] = Field(default_factory=dict)
    category_id: Optional[UUID] = None
    author_id: UUID
    is_published: bool = False
    technology_ids: Optional[List[UUID]] = None

class PublicationUpdate(PublicationCreate):
    @field_validator('category_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if v == '':
            return None
        return v

    @field_validator('source_uid', mode='before')
    @classmethod
    def empty_source_uid_to_none(cls, v):
        if v == '':
            return None
        return v


class PublicationOut(BaseModel):
    id: UUID
    title: str
    content: str
    slug: str
    content: str
    source_type: str = "article"
    source_uid: Optional[UUID] = None
    extra_data: Optional[dict] = Field(default_factory=dict)
    category_id: Optional[UUID] = None
    author_id: UUID
    is_published: bool = False
    technology_ids: Optional[List[UUID]] = None
    created_at: datetime
    author: UserOut

    model_config = ConfigDict(from_attributes=True)