from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import UUID


class CategoryOut(BaseModel):
    id: UUID = Field(
        ...,
        description="Уникальный идентификатор каталога"
    )
    title: str = Field(
        ...,
        description="Название каталога"
    )
    slug: str = Field(
        ...,
        description="ЧПУ"
    )

    model_config = ConfigDict(from_attributes=True)
