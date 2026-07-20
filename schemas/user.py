from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    email: str
    firstname: str
    lastname: str

    model_config = ConfigDict(from_attributes=True)