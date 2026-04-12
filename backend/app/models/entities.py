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
    response_format: Mapped[str] = mapped_column(String(16), default='text')
    format_example: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class StoryboardScene(Base):
    """业务上的「分镜」条目（挂在主题下）；其下再有 board_scenes（场景）与 board_shots（画面）。"""

    __tablename__ = 'storyboard_scenes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default='')
    theme_id: Mapped[int | None] = mapped_column(ForeignKey('themes.id', ondelete='SET NULL'), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default='draft')
    # AI 分镜流水线：节点列表、当前步骤等 JSON（与前端 localStorage 结构一致）
    pipeline_state: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    runs: Mapped[list['SceneRun']] = relationship(back_populates='scene')
    theme: Mapped['Theme | None'] = relationship(back_populates='storyboard_scenes')
    board_scenes: Mapped[list['BoardScene']] = relationship(
        back_populates='storyboard',
        order_by='BoardScene.sort_order',
        cascade='all, delete-orphan',
    )


class BoardScene(Base):
    """分镜下的「场景」：场景评审前/后可分栏存文本（由后端解析 AI 或用户 PATCH 写入）。"""

    __tablename__ = 'board_scenes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey('storyboard_scenes.id', ondelete='CASCADE'), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255), default='')
    before_scene_review: Mapped[str] = mapped_column(Text, default='')
    after_scene_review: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    storyboard: Mapped['StoryboardScene'] = relationship(back_populates='board_scenes')
    shots: Mapped[list['BoardShot']] = relationship(
        back_populates='board_scene',
        order_by='BoardShot.sort_order',
        cascade='all, delete-orphan',
    )


class BoardShot(Base):
    """场景下的「画面」：画面评审前/后文案分列存储。"""

    __tablename__ = 'board_shots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    board_scene_id: Mapped[int] = mapped_column(ForeignKey('board_scenes.id', ondelete='CASCADE'), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    before_frame_review: Mapped[str] = mapped_column(Text, default='')
    after_frame_review: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    board_scene: Mapped['BoardScene'] = relationship(back_populates='shots')


class SceneRun(Base):
    __tablename__ = 'scene_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey('storyboard_scenes.id'))
    # 请求中的默认/模板侧文案（与 user_input_text 分离）
    default_text: Mapped[str] = mapped_column(Text, default='')
    # 请求中的动手输入文案
    user_input_text: Mapped[str] = mapped_column(Text, default='')
    theme_id: Mapped[int | None] = mapped_column(ForeignKey('themes.id', ondelete='SET NULL'), nullable=True)
    # 实际发给模型的完整 user 消息（兼容旧逻辑，便于审计）
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
    # 业务展示名「人物设定」；列名保持 description 以兼容 API/历史数据
    description: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    storyboard_scenes: Mapped[list['StoryboardScene']] = relationship(back_populates='theme')
