from pydantic import BaseModel, Field


class PromptBase(BaseModel):
    name: str
    description: str
    response_format: str = Field(default='text', description='json | text | markdown')
    format_example: str = Field(default='', description='输出格式示例，与正文分离')


class PromptCreate(PromptBase):
    pass


class PromptUpdate(PromptBase):
    pass


class PromptEnabledUpdate(BaseModel):
    enabled: bool


class PromptUpdateWithId(PromptUpdate):
    prompt_id: int


class PromptIdBody(BaseModel):
    prompt_id: int


class PromptSetEnabledBody(BaseModel):
    prompt_id: int
    enabled: bool


class PromptRead(PromptBase):
    id: int
    enabled: bool

    class Config:
        from_attributes = True
