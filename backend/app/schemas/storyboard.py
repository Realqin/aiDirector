from datetime import datetime

from pydantic import BaseModel, field_validator


class SceneBase(BaseModel):
    name: str
    description: str = ''
    theme_id: int | None = None


class SceneCreate(SceneBase):
    pass


class SceneRead(SceneBase):
    id: int
    progress: int
    status: str
    theme_name: str = ''
    created_at: datetime | None = None

    model_config = {'from_attributes': True}


class SceneRunRequest(BaseModel):
    input_text: str
    model_id: int | None = None

    @field_validator('model_id', mode='before')
    @classmethod
    def normalize_model_id(cls, value):
        if value is None or value == '':
            return None
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            if s.isdigit():
                return int(s)
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, float):
            return int(value)
        return value


class SceneRunResponse(BaseModel):
    scene_id: int
    input_text: str
    output_text: str
    status: str
