from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TechnologyOut(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)
