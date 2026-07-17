from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PublicationCreate(BaseModel):
    title: str
    slug: str
    content: str
    source_type: str
    source_uid: Optional[str]
    metadata: dict
    category_id: UUID
    author_id: UUID
    is_published: bool

class PublicationUpdate(PublicationCreate):
    pass


class PublicationOut(BaseModel):
    id: UUID
    title: str
    content: str