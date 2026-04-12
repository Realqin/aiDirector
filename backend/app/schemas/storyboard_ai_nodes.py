"""AI 分镜各默认节点专用请求/响应（字段与 OpenAPI 模型分离，不与通用 /run 混用）。"""

from pydantic import BaseModel, Field, field_validator


def _norm_opt_id(value):
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


class StoryboardNodeAiBaseRequest(BaseModel):
    """各节点共用的请求体：default_text / input_text / 主题与分镜 id。"""

    default_text: str = ''
    input_text: str = ''
    theme_id: int | None = None
    storyboard_id: int | None = None
    model_id: int | None = None

    @field_validator('model_id', 'theme_id', 'storyboard_id', mode='before')
    @classmethod
    def _norm_ids(cls, value):
        return _norm_opt_id(value)


class StoryboardNodeAiBoundRequest(StoryboardNodeAiBaseRequest):
    """路径不含分镜 id 时，必须在 body 中显式携带 storyboard_id。"""

    storyboard_id: int


class AiNodeRunEnvelope(BaseModel):
    """每次调用都返回的运行元信息 + 模型原文。"""

    storyboard_id: int
    theme_id: int | None = None
    default_text: str = ''
    input_text: str = ''
    model_id: int | None = None
    prompt_sent: str = ''
    status: str = ''
    raw_output: str = ''
    parse_ok: bool = False


# —— 故事描述 ——


class AiStoryDescriptionResponse(AiNodeRunEnvelope):
    """story 为展示用正文：可为 JSON 中的 story 字段，或直接一段纯文本。"""

    story: str = ''


# —— 场景分解 ——


class AiSceneCardOut(BaseModel):
    title: str = ''
    text: str = ''


class AiSceneDecompositionResponse(AiNodeRunEnvelope):
    scenes: list[AiSceneCardOut] = Field(default_factory=list)


class AiSingleSceneCardResponse(AiNodeRunEnvelope):
    """场景分解：只重写一张场景卡片（scenes 数组仅 1 项时解析成功）。"""

    scene: AiSceneCardOut | None = None


# —— 场景评审 ——


class AiSceneReviewIssueItem(BaseModel):
    """问题清单展平项：嵌套 JSON 中每条「画面N问题」会变成一行 problem（多键时换行拼接）。"""

    scene: str = Field('', description='场景键名，如「场景1」')
    problem: str = Field('', description='问题描述；嵌套格式下可为「画面1问题：…」多行')
    suggestion: str = Field('', description='针对该条的修改建议')


class AiSceneReviewResponse(AiNodeRunEnvelope):
    conclusion: str = ''
    issues: list[str] = Field(
        default_factory=list,
        description='扁平问题行（兼容旧版「问题点」；若使用问题清单则每项展开为「场景：问题」与「修改建议：…」两行）',
    )
    issue_items: list[AiSceneReviewIssueItem] = Field(default_factory=list)
    original: str = ''
    revised: str = ''
    revised_scenes: list[AiSceneCardOut] = Field(
        default_factory=list,
        description='「修改后」为 scenes 结构时解析出的场景卡片（与 revised JSON 同构）',
    )


# —— 画面分解 ——


class AiFrameShotOut(BaseModel):
    description: str = ''


class AiFrameSceneOut(BaseModel):
    title: str = ''
    frames: list[AiFrameShotOut] = Field(default_factory=list)


class AiFrameDecompositionResponse(AiNodeRunEnvelope):
    scenes: list[AiFrameSceneOut] = Field(default_factory=list)


# —— 画面评审 ——


class AiFrameReviewResponse(AiNodeRunEnvelope):
    summary: str = Field(
        '',
        description='评审结论（新格式「评审结论」）或历史字段「总评」',
    )
    merits: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    optimized_scenes: list[AiFrameSceneOut] = Field(
        default_factory=list,
        description='来自「修改后.scenes」或旧键「优化分镜」；与画面分解同构',
    )
    original: str = Field(default='', description='原内容（待评审分镜全文或 JSON 字符串）')
    issue_items: list[AiSceneReviewIssueItem] = Field(
        default_factory=list,
        description='与场景评审同构的「问题清单及修改建议」',
    )


# —— 完整内容：单字段重生成（纯文本） ——


class AiFullContentSnippetResponse(AiNodeRunEnvelope):
    regenerated_text: str = ''


# —— 画面分解：单画面 description ——


class AiSingleFrameDescriptionResponse(AiNodeRunEnvelope):
    description: str = ''


class AiSingleSceneFrameResponse(AiNodeRunEnvelope):
    """单场景画面结构（scenes 数组仅 1 项时解析成功）。"""

    scene: AiFrameSceneOut | None = None
