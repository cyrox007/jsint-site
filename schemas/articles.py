from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserBrief(BaseModel):
    """Краткая информация об авторе (без пароля и прочего)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    avatar: Optional[str] = None


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str


class ArticleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime


class ArticleInList(ArticleBase):
    """Для списка — без контента, но с автором и категорией."""
    author: Optional[UserBrief] = None
    category: Optional[CategoryBrief] = None


class ArticleDetail(ArticleInList):
    """Полная версия для детальной страницы."""
    author_id: UUID
    category_id: UUID


class ArticleCreate(BaseModel):
    title: str
    slug: str
    content: str
    author_id: UUID
    category_id: UUID
    status: str = "published"