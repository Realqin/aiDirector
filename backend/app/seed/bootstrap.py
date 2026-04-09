from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import LLMModel, PromptTemplate, StoryboardScene


def bootstrap_data() -> None:
    db: Session = SessionLocal()
    try:
        if db.query(LLMModel).count() == 0:
            db.add(
                LLMModel(
                    name='GPT-4o',
                    provider='openai',
                    base_url='https://api.openai.com/v1',
                    model_name='gpt-4o',
                    api_key='replace-me',
                    enabled=False,
                )
            )
        if db.query(PromptTemplate).count() == 0:
            db.add(PromptTemplate(name='短视频-文案生成', content='请根据主题生成短视频分镜文案。', enabled=False))
        if db.query(StoryboardScene).count() == 0:
            db.add(StoryboardScene(name='城市夜景转场示例', description='用于演示分镜运行流程', progress=3, status='running'))
        db.commit()
    finally:
        db.close()
