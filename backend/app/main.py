from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.api.storyboard_ai_routes import router as storyboard_ai_router
from app.core.config import settings
from app.db.session import Base, SessionLocal, engine
from app.seed.bootstrap import bootstrap_data

Base.metadata.create_all(bind=engine)

# Lightweight migration for existing databases: align prompt_templates with ORM (enabled, no legacy version).
with SessionLocal() as db:
    db.execute(text('ALTER TABLE prompt_templates ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT FALSE'))
    db.execute(text('UPDATE prompt_templates SET enabled = FALSE WHERE enabled IS NULL'))
    # Old schema had NOT NULL "version"; model no longer maps it — inserts would fail until dropped.
    db.execute(text('ALTER TABLE prompt_templates DROP COLUMN IF EXISTS version'))
    db.execute(
        text(
            "ALTER TABLE prompt_templates ADD COLUMN IF NOT EXISTS response_format VARCHAR(16) DEFAULT 'text'"
        )
    )
    db.execute(text('ALTER TABLE prompt_templates ADD COLUMN IF NOT EXISTS format_example TEXT DEFAULT \'\''))
    db.execute(text("UPDATE prompt_templates SET response_format = 'text' WHERE response_format IS NULL"))
    db.execute(text("UPDATE prompt_templates SET format_example = '' WHERE format_example IS NULL"))
    # 占位/无效 Key 的 LLM 配置不应默认参与调用（否则节点绑定到该配置会一直 502）。
    db.execute(
        text(
            "UPDATE llm_models SET enabled = FALSE "
            "WHERE LOWER(TRIM(api_key)) IN ('replace-me', 'replace_me', 'sk-placeholder', 'your-api-key-here')"
        )
    )
    db.execute(text('ALTER TABLE storyboard_scenes ADD COLUMN IF NOT EXISTS theme_id INTEGER REFERENCES themes(id)'))
    db.execute(text("ALTER TABLE storyboard_scenes ADD COLUMN IF NOT EXISTS pipeline_state TEXT DEFAULT ''"))
    db.execute(text("ALTER TABLE scene_runs ADD COLUMN IF NOT EXISTS default_text TEXT DEFAULT ''"))
    db.execute(text("ALTER TABLE scene_runs ADD COLUMN IF NOT EXISTS user_input_text TEXT DEFAULT ''"))
    db.execute(text('ALTER TABLE scene_runs ADD COLUMN IF NOT EXISTS theme_id INTEGER REFERENCES themes(id)'))
    db.commit()

bootstrap_data()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
app.include_router(storyboard_ai_router, prefix=settings.api_prefix)


@app.get('/healthz')
def healthz() -> dict[str, str]:
    return {'status': 'ok'}
