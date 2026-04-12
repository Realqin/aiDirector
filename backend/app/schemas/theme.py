from typing import Literal

from pydantic import BaseModel, Field


class ThemeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    historical_background: str = Field(default='', max_length=2000)
    # 业务上展示为「人物设定」；JSON/API 键名仍为 description，与历史数据及下游兼容
    description: str = Field(default='', max_length=8000, description='人物设定（字段名 description）')


class ThemeCreate(ThemeBase):
    pass


class ThemeUpdate(ThemeBase):
    pass


class ThemeUpdateWithId(ThemeUpdate):
    theme_id: int


class ThemeIdBody(BaseModel):
    theme_id: int


class ThemeRead(ThemeBase):
    id: int

    model_config = {'from_attributes': True}


class ThemeRandomFill(BaseModel):
    historical_background: str
    description: str


class ThemeRandomSnippet(BaseModel):
    value: str


class ThemeAiAssistRequest(BaseModel):
    hint: str = Field(..., min_length=1, max_length=4000)
    model_id: int | None = None
    prompt_template_id: int | None = None


class ThemeAiAssistResponse(BaseModel):
    name: str = ''
    historical_background: str = ''
    description: str = ''


class ThemeAiFieldRequest(BaseModel):
    field: Literal['historical_background', 'description']
    model_id: int | None = None
    prompt_template_id: int | None = None
    theme_name: str = Field(default='', max_length=120)
    historical_background: str = Field(default='', max_length=2000)
    description: str = Field(default='', max_length=8000)
    extra_hint: str = Field(default='', max_length=2000)


class ThemeAiFieldResponse(BaseModel):
    value: str
