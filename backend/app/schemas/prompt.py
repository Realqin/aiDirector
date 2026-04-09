from pydantic import BaseModel


class PromptBase(BaseModel):
    name: str
    description: str


class PromptCreate(PromptBase):
    pass


class PromptUpdate(PromptBase):
    pass


class PromptEnabledUpdate(BaseModel):
    enabled: bool


class PromptRead(PromptBase):
    id: int
    enabled: bool

    class Config:
        from_attributes = True
