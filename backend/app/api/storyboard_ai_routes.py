"""分镜流水线各默认节点独立 AI 接口（请求/响应模型按节点区分）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import StoryboardScene
from app.schemas.storyboard_ai_nodes import (
    AiFrameDecompositionResponse,
    AiFrameReviewResponse,
    AiFrameSceneOut,
    AiFrameShotOut,
    AiFullContentSnippetResponse,
    AiSceneCardOut,
    AiSceneDecompositionResponse,
    AiSceneReviewIssueItem,
    AiSingleSceneCardResponse,
    AiSceneReviewResponse,
    AiSingleFrameDescriptionResponse,
    AiSingleSceneFrameResponse,
    AiStoryDescriptionResponse,
    StoryboardNodeAiBaseRequest,
    StoryboardNodeAiBoundRequest,
)
from app.services import ai_output_parse as ai_parse
from app.services.storyboard import run_storyboard_ai

router = APIRouter(tags=['storyboard-ai'])


def _scene_or_404(db: Session, scene_id: int) -> StoryboardScene:
    row = db.query(StoryboardScene).filter(StoryboardScene.id == scene_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='分镜不存在')
    return row


def _exec_ai(db: Session, scene: StoryboardScene, payload: StoryboardNodeAiBaseRequest):
    return run_storyboard_ai(
        db,
        scene,
        default_text=payload.default_text or '',
        input_text=payload.input_text or '',
        theme_id=payload.theme_id,
        model_id=payload.model_id,
    )


def _base_envelope(scene: StoryboardScene, run, llm, prompt_sent: str, payload: StoryboardNodeAiBaseRequest, parse_ok: bool):
    return dict(
        storyboard_id=scene.id,
        theme_id=run.theme_id,
        default_text=run.default_text or '',
        input_text=run.user_input_text or '',
        model_id=llm.id,
        prompt_sent=prompt_sent,
        status=run.status,
        raw_output=run.output_text or '',
        parse_ok=parse_ok,
    )


@router.post(
    '/storyboards/ai/story-description',
    response_model=AiStoryDescriptionResponse,
)
def ai_story_description(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, story = ai_parse.parse_story_description(raw)
    return AiStoryDescriptionResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        story=story,
    )


@router.post(
    '/storyboards/ai/scene-decomposition',
    response_model=AiSceneDecompositionResponse,
)
def ai_scene_decomposition(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, rows = ai_parse.parse_scene_decomposition(raw)
    return AiSceneDecompositionResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        scenes=[AiSceneCardOut(title=r['title'], text=r['text']) for r in rows],
    )


@router.post(
    '/storyboards/ai/single-scene-card-decomposition',
    response_model=AiSingleSceneCardResponse,
)
def ai_single_scene_card_decomposition(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    """场景分解：只重写一张场景卡片（title + text），返回 scenes 长度为 1 的 JSON。"""
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, rows = ai_parse.parse_scene_decomposition(raw)
    scene_out = None
    if ok and len(rows) == 1:
        r = rows[0]
        scene_out = AiSceneCardOut(title=str(r.get('title', '')), text=str(r.get('text', '')))
    return AiSingleSceneCardResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok and scene_out is not None),
        scene=scene_out,
    )


@router.post(
    '/storyboards/ai/scene-review',
    response_model=AiSceneReviewResponse,
)
def ai_scene_review(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, d = ai_parse.parse_scene_review(raw)
    rs = d.get('revised_scenes') or []
    ii = d.get('issue_items') or []
    return AiSceneReviewResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        conclusion=d.get('conclusion', ''),
        issues=d.get('issues', []),
        issue_items=[
            AiSceneReviewIssueItem(
                scene=str(x.get('scene', '')),
                problem=str(x.get('problem', '')),
                suggestion=str(x.get('suggestion', '')),
            )
            for x in ii
            if isinstance(x, dict)
        ],
        original=d.get('original', ''),
        revised=d.get('revised', ''),
        revised_scenes=[AiSceneCardOut(title=str(x.get('title', '')), text=str(x.get('text', ''))) for x in rs],
    )


@router.post(
    '/storyboards/ai/frame-decomposition',
    response_model=AiFrameDecompositionResponse,
)
def ai_frame_decomposition(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, rows = ai_parse.parse_frame_decomposition(raw)
    scenes = [
        AiFrameSceneOut(
            title=r['title'],
            frames=[AiFrameShotOut(description=f['description']) for f in r.get('frames', [])],
        )
        for r in rows
    ]
    return AiFrameDecompositionResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        scenes=scenes,
    )


@router.post(
    '/storyboards/ai/frame-review',
    response_model=AiFrameReviewResponse,
)
def ai_frame_review(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, d = ai_parse.parse_frame_review(raw)
    opt = d.get('optimized_scenes', [])
    optimized = [
        AiFrameSceneOut(
            title=r['title'],
            frames=[AiFrameShotOut(description=f['description']) for f in r.get('frames', [])],
        )
        for r in opt
    ]
    ii = d.get('issue_items') or []
    return AiFrameReviewResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        summary=d.get('summary', ''),
        merits=d.get('merits', []),
        suggestions=d.get('suggestions', []),
        optimized_scenes=optimized,
        original=d.get('original', ''),
        issue_items=[
            AiSceneReviewIssueItem(
                scene=str(x.get('scene', '')),
                problem=str(x.get('problem', '')),
                suggestion=str(x.get('suggestion', '')),
            )
            for x in ii
            if isinstance(x, dict)
        ],
    )


@router.post(
    '/storyboards/ai/full-content-snippet',
    response_model=AiFullContentSnippetResponse,
)
def ai_full_content_snippet(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    """完整内容节点：单格漫画或动画提示词重生成。模型须返回一条纯文本（可多行），勿 JSON；见 strip_plain_text。"""
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    regen = ai_parse.strip_plain_text(raw)
    ok = bool(regen)
    return AiFullContentSnippetResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        regenerated_text=regen,
    )


@router.post(
    '/storyboards/ai/single-scene-decomposition',
    response_model=AiSingleSceneFrameResponse,
)
def ai_single_scene_decomposition(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    """画面分解：只重写一个场景下的全部画面（返回 scenes 长度为 1 的 JSON）。"""
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, rows = ai_parse.parse_frame_decomposition(raw)
    scene_out = None
    if ok and len(rows) == 1:
        r = rows[0]
        scene_out = AiFrameSceneOut(
            title=r.get('title', ''),
            frames=[AiFrameShotOut(description=f.get('description', '')) for f in r.get('frames', [])],
        )
    return AiSingleSceneFrameResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok and scene_out is not None),
        scene=scene_out,
    )


@router.post(
    '/storyboards/ai/single-frame-description',
    response_model=AiSingleFrameDescriptionResponse,
)
def ai_single_frame_description(payload: StoryboardNodeAiBoundRequest, db: Session = Depends(get_db)):
    """画面分解：只改一条画面 description。"""
    scene = _scene_or_404(db, payload.storyboard_id)
    try:
        run, llm, prompt_sent = _exec_ai(db, scene, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    raw = run.output_text or ''
    ok, desc = ai_parse.parse_single_frame_description(raw)
    return AiSingleFrameDescriptionResponse(
        **_base_envelope(scene, run, llm, prompt_sent, payload, ok),
        description=desc,
    )
