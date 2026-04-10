from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class LLMModel(Base):
    __tablename__ = 'llm_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str] = mapped_column(String(255))
    model_name: Mapped[str] = mapped_column(String(64))
    api_key: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class PromptTemplate(Base):
    __tablename__ = 'prompt_templates'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    content: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class StoryboardScene(Base):
    __tablename__ = 'storyboard_scenes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default='')
    theme_id: Mapped[int | None] = mapped_column(ForeignKey('themes.id', ondelete='SET NULL'), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default='draft')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    runs: Mapped[list['SceneRun']] = relationship(back_populates='scene')
    theme: Mapped['Theme | None'] = relationship(back_populates='storyboard_scenes')


class SceneRun(Base):
    __tablename__ = 'scene_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey('storyboard_scenes.id'))
    input_text: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default='done')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    scene: Mapped[StoryboardScene] = relationship(back_populates='runs')


class Theme(Base):
    __tablename__ = 'themes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    historical_background: Mapped[str] = mapped_column(Text, default='')
    description: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    storyboard_scenes: Mapped[list['StoryboardScene']] = relationship(back_populates='theme')
