from sqlalchemy.orm import Session

from app.models import LLMModel, SceneRun, StoryboardScene
from app.services.llm_remote import chat_completion_user


def _resolve_llm_row(db: Session, model_id: int | None) -> LLMModel | None:
    q = db.query(LLMModel).filter(LLMModel.enabled.is_(True))
    if model_id is not None:
        row = q.filter(LLMModel.id == model_id).first()
        if row:
            return row
        return None
    return q.order_by(LLMModel.id.desc()).first()


def run_scene(db: Session, scene: StoryboardScene, user_input: str, model_id: int | None = None) -> SceneRun:
    llm = None
    if model_id is not None:
        llm = _resolve_llm_row(db, model_id)
    if llm is None:
        llm = _resolve_llm_row(db, None)
    if not llm:
        raise ValueError('请先在 LLM 配置中添加并启用至少一个模型')

    output, err = chat_completion_user(llm.base_url, llm.api_key or None, llm.model_name, user_input)
    if err:
        raise RuntimeError(err)

    run = SceneRun(
        scene_id=scene.id,
        input_text=user_input,
        output_text=output or '',
        status='done',
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
