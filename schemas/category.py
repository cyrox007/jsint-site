from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str
    slug: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    parent_id: Optional[UUID] = None
