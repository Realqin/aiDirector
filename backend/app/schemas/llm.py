from pydantic import BaseModel


class LLMModelBase(BaseModel):
    name: str
    provider: str
    base_url: str
    model_name: str
    api_key: str
    enabled: bool = True


class LLMModelCreate(LLMModelBase):
    pass


class LLMModelRead(LLMModelBase):
    id: int

    class Config:
        from_attributes = True


class LLMModelUpdate(LLMModelBase):
    pass


class LLMModelEnabledUpdate(BaseModel):
    enabled: bool


class LLMModelUpdateWithId(LLMModelUpdate):
    model_id: int


class LLMModelIdBody(BaseModel):
    model_id: int


class LLMModelSetEnabledBody(BaseModel):
    model_id: int
    enabled: bool


class RemoteModelsRequest(BaseModel):
    base_url: str
    api_key: str = ''


class RemoteModelsResponse(BaseModel):
    models: list[str]
    error: str | None = None


class TestConnectionRequest(BaseModel):
    base_url: str
    api_key: str = ''
    model_name: str | None = None


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str
