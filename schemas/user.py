from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    email: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
