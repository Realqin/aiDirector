from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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


def _normalize_optional_int_id(value):
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


class StoryboardByIdBody(BaseModel):
    storyboard_id: int


class StoryboardPipelineNodeBody(BaseModel):
    storyboard_id: int
    node_id: str = Field(..., min_length=1, description='流水线节点 id，与前端 nodes[].id 一致')


class StoryboardUpdateBody(SceneCreate):
    storyboard_id: int


class StoryboardAiRunRequest(BaseModel):
    """提交大模型执行：默认文案与手工输入分离，并显式携带主题/分镜 id。"""

    default_text: str = ''
    input_text: str = ''
    theme_id: int | None = None
    storyboard_id: int | None = None
    model_id: int | None = None
    theme_context_mode: Literal['full', 'appearance_only', 'omit'] = 'full'

    @field_validator('model_id', 'theme_id', 'storyboard_id', mode='before')
    @classmethod
    def normalize_optional_ids(cls, value):
        return _normalize_optional_int_id(value)


class StoryboardAiRunPostRequest(StoryboardAiRunRequest):
    """通用 /run：必须在 body 中携带分镜 id（路径不含数字 id）。"""

    storyboard_id: int


class StoryboardAiRunResponse(BaseModel):
    """与请求字段对齐，并返回实际下发给模型的全文与所用模型 id。"""

    storyboard_id: int
    theme_id: int | None = None
    default_text: str = ''
    input_text: str = ''
    model_id: int | None = None
    prompt_sent: str = ''
    output_text: str = ''
    status: str = ''


# —— 分镜结构化树（主题 → 分镜 → 场景 → 画面，字段入库，接口不传大段 JSON）——


class BoardShotRead(BaseModel):
    id: int
    sort_order: int
    before_frame_review: str = ''
    after_frame_review: str = ''

    model_config = {'from_attributes': True}


class BoardSceneRead(BaseModel):
    id: int
    sort_order: int
    title: str = ''
    before_scene_review: str = ''
    after_scene_review: str = ''
    shots: list[BoardShotRead] = []

    model_config = {'from_attributes': True}


class StoryboardTreeRead(BaseModel):
    """单个分镜（storyboard_scenes 一行）及其下的场景/画面树。"""

    id: int
    name: str
    description: str = ''
    theme_id: int | None = None
    theme_name: str = ''
    progress: int
    status: str
    scenes: list[BoardSceneRead] = []


class PipelineStatePayload(BaseModel):
    """运行页流水线状态（节点内容、游标等），与前端 persist 结构一致。"""

    active_node_index: int = 0
    max_unlocked_index: int = 0
    nodes: list[Any] = Field(default_factory=list)


class StoryboardPipelineStateWriteBody(PipelineStatePayload):
    storyboard_id: int


# —— 场景 → 画面 树（字段名显式，供「节点查询」与 AI 上下文）——


class SceneFrameTreeShot(BaseModel):
    """分镜下的一个画面（镜头）。"""

    shot_id: int
    sort_order: int
    before_frame_review: str = ''
    after_frame_review: str = ''


class SceneFrameTreeScene(BaseModel):
    """分镜下的一个场景，内含画面列表。"""

    scene_id: int
    sort_order: int
    title: str = ''
    before_scene_review: str = ''
    after_scene_review: str = ''
    shots: list[SceneFrameTreeShot] = Field(default_factory=list)


class ThemeBriefRead(BaseModel):
    theme_id: int
    name: str
    historical_background: str = ''
    # 与 Theme.description 一致，业务含义为「人物设定」
    description: str = ''


class StoryboardBriefRead(BaseModel):
    storyboard_id: int
    name: str
    description: str = ''
    theme_id: int | None = None


class StoryboardAiRunSummaryRead(BaseModel):
    """运行页：仅分镜摘要 + 主题（不含场景树、流水线）。"""

    storyboard: StoryboardBriefRead
    theme: ThemeBriefRead | None = None


class AiRunSceneFrameTreeRead(BaseModel):
    """运行页：仅入库的场景→画面树（与节点无关）。"""

    scenes: list[SceneFrameTreeScene] = Field(default_factory=list)


class PipelineNodeByNodeIdRead(BaseModel):
    """按流水线节点 id 返回单条节点；node_id 与前端 nodes[].id 一致，非步序号。"""

    node_id: str = Field(description='流水线节点 id（字符串）')
    pipeline_step_index: int = Field(description='该节点在 pipeline.nodes 数组中的下标，从 0 起')
    node: Any = Field(description='该节点的完整对象（与持久化结构一致）')
