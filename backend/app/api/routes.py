import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.session import get_db
from app.models import BoardScene, LLMModel, PromptTemplate, SceneRun, StoryboardScene, Theme
from app.schemas.llm import (
    LLMModelCreate,
    LLMModelIdBody,
    LLMModelRead,
    LLMModelSetEnabledBody,
    LLMModelUpdateWithId,
    RemoteModelsRequest,
    RemoteModelsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services.llm_remote import fetch_remote_model_ids, test_connection
from app.services.prompt_compose import normalize_response_format
from app.schemas.prompt import (
    PromptCreate,
    PromptIdBody,
    PromptRead,
    PromptSetEnabledBody,
    PromptUpdateWithId,
)
from app.schemas.storyboard import (
    AiRunSceneFrameTreeRead,
    BoardSceneRead,
    BoardShotRead,
    PipelineNodeByNodeIdRead,
    PipelineStatePayload,
    SceneCreate,
    SceneFrameTreeScene,
    SceneFrameTreeShot,
    SceneRead,
    StoryboardAiRunPostRequest,
    StoryboardAiRunResponse,
    StoryboardAiRunSummaryRead,
    StoryboardBriefRead,
    StoryboardByIdBody,
    StoryboardPipelineNodeBody,
    StoryboardPipelineStateWriteBody,
    StoryboardTreeRead,
    StoryboardUpdateBody,
    ThemeBriefRead,
)
from app.schemas.theme import (
    ThemeAiAssistRequest,
    ThemeAiAssistResponse,
    ThemeAiFieldRequest,
    ThemeAiFieldResponse,
    ThemeCreate,
    ThemeIdBody,
    ThemeRandomFill,
    ThemeRandomSnippet,
    ThemeRead,
    ThemeUpdateWithId,
)
from app.services.storyboard import run_storyboard_ai
from app.services.theme_ai import theme_ai_assist, theme_ai_field

_THEME_RANDOM_DISABLED_DETAIL = (
    '已取消无模型的本地随机文案。请通过「LLM 配置」启用模型，在主题弹窗「配置」中为槽位选择模型与提示词模板后，'
    '使用「AI 生成」调用大模型；或手动填写。'
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


@router.post('/llm/models/update', response_model=LLMModelRead)
def update_model(payload: LLMModelUpdateWithId, db: Session = Depends(get_db)):
    model_id = payload.model_id
    row = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')
    body = payload.model_dump(exclude={'model_id'})
    exists = db.query(LLMModel).filter(LLMModel.name == body['name'], LLMModel.id != model_id).first()
    if exists:
        raise HTTPException(status_code=400, detail='模型名称已存在')
    for key, val in body.items():
        setattr(row, key, val)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post('/llm/models/set-enabled', response_model=LLMModelRead)
def update_model_enabled(payload: LLMModelSetEnabledBody, db: Session = Depends(get_db)):
    row = db.query(LLMModel).filter(LLMModel.id == payload.model_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')
    row.enabled = payload.enabled
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post('/llm/models/delete')
def delete_model(payload: LLMModelIdBody, db: Session = Depends(get_db)):
    row = db.query(LLMModel).filter(LLMModel.id == payload.model_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')
    db.delete(row)
    db.commit()
    return {'ok': True}


def _prompt_row_to_read(row: PromptTemplate) -> PromptRead:
    return PromptRead(
        id=row.id,
        name=row.name,
        description=row.content,
        response_format=normalize_response_format(row.response_format),
        format_example=row.format_example or '',
        enabled=row.enabled,
    )


@router.get('/prompts', response_model=list[PromptRead])
def list_prompts(db: Session = Depends(get_db)):
    rows = db.query(PromptTemplate).order_by(PromptTemplate.id.desc()).all()
    return [_prompt_row_to_read(row) for row in rows]


@router.post('/prompts', response_model=PromptRead)
def create_prompt(payload: PromptCreate, db: Session = Depends(get_db)):
    exists = db.query(PromptTemplate).filter(PromptTemplate.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail='提示词模板已存在')
    row = PromptTemplate(
        name=payload.name,
        content=payload.description,
        response_format=normalize_response_format(payload.response_format),
        format_example=(payload.format_example or '').strip(),
        enabled=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _prompt_row_to_read(row)


@router.post('/prompts/update', response_model=PromptRead)
def update_prompt(payload: PromptUpdateWithId, db: Session = Depends(get_db)):
    prompt_id = payload.prompt_id
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
    row.response_format = normalize_response_format(payload.response_format)
    row.format_example = (payload.format_example or '').strip()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _prompt_row_to_read(row)


@router.post('/prompts/set-enabled', response_model=PromptRead)
def update_prompt_enabled(payload: PromptSetEnabledBody, db: Session = Depends(get_db)):
    row = db.query(PromptTemplate).filter(PromptTemplate.id == payload.prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='提示词模板不存在')
    row.enabled = payload.enabled
    db.add(row)
    db.commit()
    db.refresh(row)
    return _prompt_row_to_read(row)


@router.post('/prompts/delete')
def delete_prompt(payload: PromptIdBody, db: Session = Depends(get_db)):
    row = db.query(PromptTemplate).filter(PromptTemplate.id == payload.prompt_id).first()
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


# 静态子路径须写在可能与之冲突的通配路径之前（当前主题相关路径均不含路径参数 id）。
@router.get('/themes/random-fill', response_model=ThemeRandomFill)
def theme_random_fill():
    raise HTTPException(status_code=400, detail=_THEME_RANDOM_DISABLED_DETAIL)


@router.get('/themes/random-historical-background', response_model=ThemeRandomSnippet)
def theme_random_historical_background():
    raise HTTPException(status_code=400, detail=_THEME_RANDOM_DISABLED_DETAIL)


@router.get('/themes/random-description', response_model=ThemeRandomSnippet)
def theme_random_description():
    raise HTTPException(status_code=400, detail=_THEME_RANDOM_DISABLED_DETAIL)


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


@router.post('/themes/update', response_model=ThemeRead)
def update_theme(payload: ThemeUpdateWithId, db: Session = Depends(get_db)):
    theme_id = payload.theme_id
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


@router.post('/themes/delete')
def delete_theme(payload: ThemeIdBody, db: Session = Depends(get_db)):
    row = db.query(Theme).filter(Theme.id == payload.theme_id).first()
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


def _storyboard_to_tree_read(sb: StoryboardScene) -> StoryboardTreeRead:
    scenes_sorted = sorted(sb.board_scenes or [], key=lambda x: (x.sort_order, x.id))
    scenes_out: list[BoardSceneRead] = []
    for bs in scenes_sorted:
        shots_sorted = sorted(bs.shots or [], key=lambda x: (x.sort_order, x.id))
        scenes_out.append(
            BoardSceneRead(
                id=bs.id,
                sort_order=bs.sort_order,
                title=bs.title or '',
                before_scene_review=bs.before_scene_review or '',
                after_scene_review=bs.after_scene_review or '',
                shots=[
                    BoardShotRead(
                        id=sh.id,
                        sort_order=sh.sort_order,
                        before_frame_review=sh.before_frame_review or '',
                        after_frame_review=sh.after_frame_review or '',
                    )
                    for sh in shots_sorted
                ],
            )
        )
    return StoryboardTreeRead(
        id=sb.id,
        name=sb.name,
        description=sb.description or '',
        theme_id=sb.theme_id,
        theme_name=sb.theme.name if sb.theme else '',
        progress=sb.progress,
        status=sb.status,
        scenes=scenes_out,
    )


def _storyboard_to_scene_frame_tree(sb: StoryboardScene) -> list[SceneFrameTreeScene]:
    """场景 → 画面 多层列表，字段名与 REST 契约一致。"""
    scenes_sorted = sorted(sb.board_scenes or [], key=lambda x: (x.sort_order, x.id))
    out: list[SceneFrameTreeScene] = []
    for bs in scenes_sorted:
        shots_sorted = sorted(bs.shots or [], key=lambda x: (x.sort_order, x.id))
        out.append(
            SceneFrameTreeScene(
                scene_id=bs.id,
                sort_order=bs.sort_order,
                title=bs.title or '',
                before_scene_review=bs.before_scene_review or '',
                after_scene_review=bs.after_scene_review or '',
                shots=[
                    SceneFrameTreeShot(
                        shot_id=sh.id,
                        sort_order=sh.sort_order,
                        before_frame_review=sh.before_frame_review or '',
                        after_frame_review=sh.after_frame_review or '',
                    )
                    for sh in shots_sorted
                ],
            )
        )
    return out


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


@router.post('/storyboards/tree', response_model=StoryboardTreeRead)
def get_storyboard_tree(payload: StoryboardByIdBody, db: Session = Depends(get_db)):
    """分镜下场景→画面树状数据（字段已入库，非整段 JSON）。"""
    scene_id = payload.storyboard_id
    row = (
        db.query(StoryboardScene)
        .options(
            joinedload(StoryboardScene.theme),
            selectinload(StoryboardScene.board_scenes).selectinload(BoardScene.shots),
        )
        .filter(StoryboardScene.id == scene_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    return _storyboard_to_tree_read(row)


@router.post('/storyboards/ai-run/summary', response_model=StoryboardAiRunSummaryRead)
def get_storyboard_ai_run_summary(payload: StoryboardByIdBody, db: Session = Depends(get_db)):
    """运行页调试：仅分镜摘要 + 主题。"""
    scene_id = payload.storyboard_id
    row = (
        db.query(StoryboardScene)
        .options(joinedload(StoryboardScene.theme))
        .filter(StoryboardScene.id == scene_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    theme_out = None
    if row.theme:
        theme_out = ThemeBriefRead(
            theme_id=row.theme.id,
            name=row.theme.name,
            historical_background=row.theme.historical_background or '',
            description=row.theme.description or '',
        )
    sb = StoryboardBriefRead(
        storyboard_id=row.id,
        name=row.name,
        description=row.description or '',
        theme_id=row.theme_id,
    )
    return StoryboardAiRunSummaryRead(storyboard=sb, theme=theme_out)


@router.post('/storyboards/ai-run/scene-frame-tree', response_model=AiRunSceneFrameTreeRead)
def get_storyboard_ai_run_scene_frame_tree(payload: StoryboardByIdBody, db: Session = Depends(get_db)):
    """运行页调试：仅入库场景→画面树（与当前选中的流水线节点无关）。"""
    scene_id = payload.storyboard_id
    row = (
        db.query(StoryboardScene)
        .options(
            joinedload(StoryboardScene.theme),
            selectinload(StoryboardScene.board_scenes).selectinload(BoardScene.shots),
        )
        .filter(StoryboardScene.id == scene_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    return AiRunSceneFrameTreeRead(scenes=_storyboard_to_scene_frame_tree(row))


@router.post('/storyboards/ai-run/pipeline-node', response_model=PipelineNodeByNodeIdRead)
def get_storyboard_ai_run_pipeline_node(payload: StoryboardPipelineNodeBody, db: Session = Depends(get_db)):
    """运行页调试：仅一条流水线节点。用 body 中的 node_id 定位。"""
    scene_id = payload.storyboard_id
    node_id = payload.node_id
    row = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    raw = (row.pipeline_state or '').strip()
    if not raw:
        raise HTTPException(status_code=404, detail='流水线暂无数据')
    try:
        pl = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f'流水线 JSON 无效：{e}') from e
    nodes = pl.get('nodes')
    if not isinstance(nodes, list):
        raise HTTPException(status_code=500, detail='流水线缺少 nodes 数组')
    for i, n in enumerate(nodes):
        if isinstance(n, dict) and n.get('id') == node_id:
            return PipelineNodeByNodeIdRead(node_id=node_id, pipeline_step_index=i, node=n)
    raise HTTPException(status_code=404, detail=f'未找到 node_id={node_id!r} 的流水线节点')


@router.post('/storyboards/pipeline-state/load', response_model=PipelineStatePayload)
def get_storyboard_pipeline_state(payload: StoryboardByIdBody, db: Session = Depends(get_db)):
    """AI 分镜运行页流水线状态（节点输入输出、当前步骤等）。"""
    scene_id = payload.storyboard_id
    row = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    raw = (row.pipeline_state or '').strip()
    if not raw:
        return PipelineStatePayload()
    try:
        return PipelineStatePayload.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError, TypeError):
        return PipelineStatePayload()


@router.post('/storyboards/pipeline-state/save', response_model=PipelineStatePayload)
def put_storyboard_pipeline_state(payload: StoryboardPipelineStateWriteBody, db: Session = Depends(get_db)):
    scene_id = payload.storyboard_id
    row = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    inner = PipelineStatePayload.model_validate(payload.model_dump(exclude={'storyboard_id'}))
    body = inner.model_dump(mode='json')
    row.pipeline_state = json.dumps(body, ensure_ascii=False)
    n = len(inner.nodes)
    if n > 0:
        row.progress = min(100, max(0, round(100 * (inner.max_unlocked_index + 1) / n)))
    db.add(row)
    db.commit()
    db.refresh(row)
    return PipelineStatePayload.model_validate(json.loads(row.pipeline_state or '{}'))


@router.post('/storyboards/update', response_model=SceneRead)
def update_storyboard(payload: StoryboardUpdateBody, db: Session = Depends(get_db)):
    scene_id = payload.storyboard_id
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


@router.post('/storyboards/delete')
def delete_storyboard(payload: StoryboardByIdBody, db: Session = Depends(get_db)):
    scene_id = payload.storyboard_id
    scene = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail='分镜不存在')
    db.query(SceneRun).filter(SceneRun.scene_id == scene_id).delete(synchronize_session=False)
    db.delete(scene)
    db.commit()
    return {'ok': True}


@router.post('/storyboards/run', response_model=StoryboardAiRunResponse)
def execute_storyboard(payload: StoryboardAiRunPostRequest, db: Session = Depends(get_db)):
    """自定义节点或非内置步骤时使用；内置节点请走 /storyboards/ai/* 专用接口。"""
    scene = db.query(StoryboardScene).filter(StoryboardScene.id == payload.storyboard_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail='分镜不存在')
    try:
        run, llm, prompt_sent = run_storyboard_ai(
            db,
            scene,
            default_text=payload.default_text or '',
            input_text=payload.input_text or '',
            theme_id=payload.theme_id,
            model_id=payload.model_id,
            theme_context_mode=payload.theme_context_mode or 'full',
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return StoryboardAiRunResponse(
        storyboard_id=scene.id,
        theme_id=run.theme_id,
        default_text=run.default_text or '',
        input_text=run.user_input_text or '',
        model_id=llm.id,
        prompt_sent=prompt_sent,
        output_text=run.output_text,
        status=run.status,
    )
