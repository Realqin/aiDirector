from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import LLMModel, PromptTemplate, SceneRun, StoryboardScene, Theme
from app.schemas.llm import (
    LLMModelCreate,
    LLMModelEnabledUpdate,
    LLMModelRead,
    LLMModelUpdate,
    RemoteModelsRequest,
    RemoteModelsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services.llm_remote import fetch_remote_model_ids, test_connection
from app.schemas.prompt import PromptCreate, PromptEnabledUpdate, PromptRead, PromptUpdate
from app.schemas.storyboard import SceneCreate, SceneRead, SceneRunRequest, SceneRunResponse
from app.schemas.theme import (
    ThemeAiAssistRequest,
    ThemeAiAssistResponse,
    ThemeAiFieldRequest,
    ThemeAiFieldResponse,
    ThemeCreate,
    ThemeRandomFill,
    ThemeRandomSnippet,
    ThemeRead,
    ThemeUpdate,
)
from app.services.storyboard import run_scene
from app.services.theme_ai import (
    random_description,
    random_historical_background,
    random_theme_fill,
    theme_ai_assist,
    theme_ai_field,
)

router = APIRouter()


@router.get('/llm/models', response_model=list[LLMModelRead])
def list_models(db: Session = Depends(get_db)):
    return db.query(LLMModel).order_by(LLMModel.id.desc()).all()


@router.post('/llm/remote-models', response_model=RemoteModelsResponse)
def list_remote_models(payload: RemoteModelsRequest):
    ids, err = fetch_remote_model_ids(payload.base_url, payload.api_key or None)
    return RemoteModelsResponse(models=ids, error=err)


@router.post('/llm/test-connection', response_model=TestConnectionResponse)
def llm_test_connection(payload: TestConnectionRequest):
    ok, msg = test_connection(payload.base_url, payload.api_key or None, payload.model_name)
    return TestConnectionResponse(ok=ok, message=msg)


@router.post('/llm/models', response_model=LLMModelRead)
def create_model(payload: LLMModelCreate, db: Session = Depends(get_db)):
    exists = db.query(LLMModel).filter(LLMModel.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail='模型名称已存在')
    row = LLMModel(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put('/llm/models/{model_id}', response_model=LLMModelRead)
def update_model(model_id: int, payload: LLMModelUpdate, db: Session = Depends(get_db)):
    row = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')
    exists = db.query(LLMModel).filter(LLMModel.name == payload.name, LLMModel.id != model_id).first()
    if exists:
        raise HTTPException(status_code=400, detail='模型名称已存在')
    for key, val in payload.model_dump().items():
        setattr(row, key, val)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch('/llm/models/{model_id}/enabled', response_model=LLMModelRead)
def update_model_enabled(model_id: int, payload: LLMModelEnabledUpdate, db: Session = Depends(get_db)):
    row = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')
    row.enabled = payload.enabled
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete('/llm/models/{model_id}')
def delete_model(model_id: int, db: Session = Depends(get_db)):
    row = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')
    db.delete(row)
    db.commit()
    return {'ok': True}


@router.get('/prompts', response_model=list[PromptRead])
def list_prompts(db: Session = Depends(get_db)):
    rows = db.query(PromptTemplate).order_by(PromptTemplate.id.desc()).all()
    return [PromptRead(id=row.id, name=row.name, description=row.content, enabled=row.enabled) for row in rows]


@router.post('/prompts', response_model=PromptRead)
def create_prompt(payload: PromptCreate, db: Session = Depends(get_db)):
    exists = db.query(PromptTemplate).filter(PromptTemplate.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail='提示词模板已存在')
    row = PromptTemplate(name=payload.name, content=payload.description, enabled=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return PromptRead(id=row.id, name=row.name, description=row.content, enabled=row.enabled)


@router.put('/prompts/{prompt_id}', response_model=PromptRead)
def update_prompt(prompt_id: int, payload: PromptUpdate, db: Session = Depends(get_db)):
    row = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='提示词模板不存在')
    exists = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.name == payload.name, PromptTemplate.id != prompt_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail='提示词模板已存在')
    row.name = payload.name
    row.content = payload.description
    db.add(row)
    db.commit()
    db.refresh(row)
    return PromptRead(id=row.id, name=row.name, description=row.content, enabled=row.enabled)


@router.patch('/prompts/{prompt_id}/enabled', response_model=PromptRead)
def update_prompt_enabled(prompt_id: int, payload: PromptEnabledUpdate, db: Session = Depends(get_db)):
    row = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='提示词模板不存在')
    row.enabled = payload.enabled
    db.add(row)
    db.commit()
    db.refresh(row)
    return PromptRead(id=row.id, name=row.name, description=row.content, enabled=row.enabled)


@router.delete('/prompts/{prompt_id}')
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    row = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='提示词模板不存在')
    db.delete(row)
    db.commit()
    return {'ok': True}


@router.get('/themes', response_model=list[ThemeRead])
def list_themes(db: Session = Depends(get_db)):
    return db.query(Theme).order_by(Theme.id.desc()).all()


@router.post('/themes', response_model=ThemeRead)
def create_theme(payload: ThemeCreate, db: Session = Depends(get_db)):
    exists = db.query(Theme).filter(Theme.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail='主题名称已存在')
    row = Theme(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# 静态子路径须写在 /themes/{theme_id} 之前，避免部分路由实现把片段当成 id 匹配。
@router.get('/themes/random-fill', response_model=ThemeRandomFill)
def theme_random_fill():
    return ThemeRandomFill(**random_theme_fill())


@router.get('/themes/random-historical-background', response_model=ThemeRandomSnippet)
def theme_random_historical_background():
    return ThemeRandomSnippet(value=random_historical_background())


@router.get('/themes/random-description', response_model=ThemeRandomSnippet)
def theme_random_description():
    return ThemeRandomSnippet(value=random_description())


@router.post('/themes/ai-field', response_model=ThemeAiFieldResponse)
def theme_ai_field_route(payload: ThemeAiFieldRequest, db: Session = Depends(get_db)):
    value, err = theme_ai_field(
        db,
        payload.field,
        model_id=payload.model_id,
        prompt_template_id=payload.prompt_template_id,
        theme_name=payload.theme_name,
        historical_background=payload.historical_background,
        description=payload.description,
        extra_hint=payload.extra_hint,
    )
    if err:
        raise HTTPException(status_code=400, detail=err) from None
    return ThemeAiFieldResponse(value=value)


@router.post('/themes/ai-assist', response_model=ThemeAiAssistResponse)
def theme_ai_assist_route(payload: ThemeAiAssistRequest, db: Session = Depends(get_db)):
    data, err = theme_ai_assist(
        db,
        payload.hint,
        model_id=payload.model_id,
        prompt_template_id=payload.prompt_template_id,
    )
    if err:
        raise HTTPException(status_code=400, detail=err) from None
    return ThemeAiAssistResponse(**data)


@router.put('/themes/{theme_id}', response_model=ThemeRead)
def update_theme(theme_id: int, payload: ThemeUpdate, db: Session = Depends(get_db)):
    row = db.query(Theme).filter(Theme.id == theme_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='主题不存在')
    exists = db.query(Theme).filter(Theme.name == payload.name, Theme.id != theme_id).first()
    if exists:
        raise HTTPException(status_code=400, detail='主题名称已存在')
    row.name = payload.name
    row.historical_background = payload.historical_background
    row.description = payload.description
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete('/themes/{theme_id}')
def delete_theme(theme_id: int, db: Session = Depends(get_db)):
    row = db.query(Theme).filter(Theme.id == theme_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='主题不存在')
    db.delete(row)
    db.commit()
    return {'ok': True}


def _validate_theme_id(db: Session, theme_id: int | None) -> None:
    if theme_id is None:
        return
    t = db.query(Theme).filter(Theme.id == theme_id).first()
    if not t:
        raise HTTPException(status_code=400, detail='主题不存在')


def _scene_to_read(scene: StoryboardScene) -> SceneRead:
    return SceneRead(
        id=scene.id,
        name=scene.name,
        description=scene.description or '',
        theme_id=scene.theme_id,
        theme_name=scene.theme.name if scene.theme else '',
        progress=scene.progress,
        status=scene.status,
        created_at=scene.created_at,
    )


@router.get('/storyboards', response_model=list[SceneRead])
def list_storyboards(db: Session = Depends(get_db)):
    rows = (
        db.query(StoryboardScene)
        .options(joinedload(StoryboardScene.theme))
        .order_by(StoryboardScene.id.desc())
        .all()
    )
    return [_scene_to_read(s) for s in rows]


@router.post('/storyboards', response_model=SceneRead)
def create_storyboard(payload: SceneCreate, db: Session = Depends(get_db)):
    exists = db.query(StoryboardScene).filter(StoryboardScene.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail='分镜名称已存在')
    _validate_theme_id(db, payload.theme_id)
    row = StoryboardScene(
        name=payload.name,
        description=payload.description,
        theme_id=payload.theme_id,
        progress=0,
        status='draft',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    scene = (
        db.query(StoryboardScene)
        .options(joinedload(StoryboardScene.theme))
        .filter(StoryboardScene.id == row.id)
        .first()
    )
    return _scene_to_read(scene)


@router.put('/storyboards/{scene_id}', response_model=SceneRead)
def update_storyboard(scene_id: int, payload: SceneCreate, db: Session = Depends(get_db)):
    scene = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail='分镜不存在')
    exists = (
        db.query(StoryboardScene)
        .filter(StoryboardScene.name == payload.name, StoryboardScene.id != scene_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail='分镜名称已存在')
    _validate_theme_id(db, payload.theme_id)
    scene.name = payload.name
    scene.description = payload.description
    scene.theme_id = payload.theme_id
    db.add(scene)
    db.commit()
    db.refresh(scene)
    scene = (
        db.query(StoryboardScene)
        .options(joinedload(StoryboardScene.theme))
        .filter(StoryboardScene.id == scene_id)
        .first()
    )
    return _scene_to_read(scene)


@router.delete('/storyboards/{scene_id}')
def delete_storyboard(scene_id: int, db: Session = Depends(get_db)):
    scene = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail='分镜不存在')
    db.query(SceneRun).filter(SceneRun.scene_id == scene_id).delete(synchronize_session=False)
    db.delete(scene)
    db.commit()
    return {'ok': True}


@router.post('/storyboards/{scene_id}/run', response_model=SceneRunResponse)
def execute_storyboard(scene_id: int, payload: SceneRunRequest, db: Session = Depends(get_db)):
    scene = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail='分镜不存在')
    try:
        run = run_scene(db, scene, payload.input_text, payload.model_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return SceneRunResponse(scene_id=scene.id, input_text=run.input_text, output_text=run.output_text, status=run.status)
