import re

from sqlalchemy.orm import Session

from app.models import LLMModel, SceneRun, StoryboardScene, Theme
from app.services.llm_remote import chat_completion_user


def _resolve_llm_row(db: Session, model_id: int | None) -> LLMModel | None:
    """model_id 有值时只接受「存在且已启用」的该条；不再静默改用其它模型。"""
    q_enabled = db.query(LLMModel).filter(LLMModel.enabled.is_(True))
    if model_id is not None:
        return q_enabled.filter(LLMModel.id == model_id).first()
    return q_enabled.order_by(LLMModel.id.desc()).first()


THEME_WORLD_HEADER = (
    '【世界观与主题设定 — 须全文遵守】\n'
    '以下为当前 AI 分镜任务所属项目的大环境：时代感、叙事基调、人物与关系、视觉风格等均应以此为锚。'
    '你在本次对话中写出的故事、场景、画面、台词、评审意见、图像/视频提示词等，均须与下列设定自洽，'
    '不得引入与之矛盾的人物身份、阵营、时代细节或世界观；不得无故跳脱已给出的基调去「另起炉灶」。'
    '若上游节点素材与设定有轻微冲突，以本设定为准并做合理调和。'
)

THEME_MISSING_ADVISORY = (
    '【重要提示】当前分镜未关联有效主题，或主题库中暂无对应记录。生成内容易与项目整体设定脱节。'
    '请先在分镜管理中为本分镜选择主题，并尽量完善主题的「描述 / 历史背景」。'
    '若仍继续生成，请保持单条内容内部自洽，避免无依据地扩张世界观或编造与业务无关的设定。'
)


def build_theme_context_block(db: Session, theme_id: int | None) -> str:
    """拼出置于每次 LLM 请求最前的主题与世界观约束（所有分镜节点共用）。"""
    if theme_id is None:
        return ''
    t = db.query(Theme).filter(Theme.id == theme_id).first()
    if not t:
        return ''
    parts = [THEME_WORLD_HEADER.strip(), f'【主题名称】{t.name.strip() or "（未命名）"}']
    hb = (t.historical_background or '').strip()
    parts.append('【历史背景】\n' + (hb if hb else '（暂无；请勿编造与主题名称明显矛盾的具体年代或史实，可与名称弱关联）'))
    desc = (t.description or '').strip()
    parts.append('【人物设定】\n' + (desc if desc else '（暂无；人物关系与视觉基调以主题名称为纲，勿凭空增加无依据设定）'))
    parts.append(
        '【执行要求】以上共同构成「大环境」。其后用户消息中的任务说明、上游节点输出及补充说明，'
        '均须在与上述设定一致的前提下展开；禁止脱离该大环境进行无关创作。'
    )
    return '\n'.join(parts)


CHAR_APPEARANCE_HEADER = '【角色长相（摘自主题「人物设定」）】'

_THEME_SECTION_HEAD = re.compile(r'^#{1,6}\s+', re.MULTILINE)


def extract_character_appearance_from_description(description: str) -> str:
    """从主题人物设定正文中尽量只取出「角色长相」段落；无显式标记则返回空（不把整段人物设定发给模型）。"""
    s = (description or '').strip()
    if not s:
        return ''
    # 1) 【角色长相】… 直到下一个【xxx】或文末
    m = re.search(r'【\s*角色长相\s*】\s*\n?([\s\S]*?)(?=\n\s*【[^】]+】\s*|\Z)', s)
    if m:
        block = m.group(1).strip()
        if block:
            return block
    lines = s.splitlines()
    # 2) Markdown 标题 ### 角色长相
    for i, line in enumerate(lines):
        t = line.strip()
        if re.match(r'^#{1,6}\s*角色长相\s*$', t):
            buf: list[str] = []
            for j in range(i + 1, len(lines)):
                L = lines[j]
                st = L.strip()
                if _THEME_SECTION_HEAD.match(L) or (st.startswith('【') and '】' in st):
                    break
                if re.match(r'^[^\s【#][^：:]{0,20}[：:]\s*\S', st) and buf:
                    break
                buf.append(L)
            out = '\n'.join(buf).strip()
            if out:
                return out
    # 3) 行首「角色长相：」及其后连续非空行（遇新小节标题则停）
    for i, line in enumerate(lines):
        t = line.strip()
        sm = re.match(r'^角色长相\s*([：:])\s*(.*)$', t)
        if not sm:
            continue
        first = (sm.group(2) or '').strip()
        buf = [first] if first else []
        for j in range(i + 1, len(lines)):
            L = lines[j]
            st = L.strip()
            if not st:
                break
            if st.startswith('【') and '】' in st:
                break
            if _THEME_SECTION_HEAD.match(L):
                break
            buf.append(L)
        out = '\n'.join(buf).strip()
        if out:
            return out
    return ''


def build_theme_character_appearance_block(db: Session, theme_id: int | None) -> str:
    """完整内容生成等场景：仅附加人物设定中的「角色长相」节选，不含历史背景与全文人物设定。"""
    if theme_id is None:
        return ''
    t = db.query(Theme).filter(Theme.id == theme_id).first()
    if not t:
        return ''
    ap = extract_character_appearance_from_description(t.description or '')
    if not ap.strip():
        return ''
    name = (t.name or '').strip() or '（未命名）'
    return f'{CHAR_APPEARANCE_HEADER}\n【主题名称】{name}\n{ap.strip()}'


def compose_prompt_sent(*, theme_block: str, default_text: str, input_text: str) -> str:
    chunks = []
    tb = (theme_block or '').strip()
    if tb:
        chunks.append(tb)
    dt = (default_text or '').strip()
    if dt:
        chunks.append(dt)
    ut = (input_text or '').strip()
    if ut:
        chunks.append(ut)
    return '\n\n'.join(chunks)


def run_storyboard_ai(
    db: Session,
    scene: StoryboardScene,
    *,
    default_text: str,
    input_text: str,
    theme_id: int | None,
    model_id: int | None = None,
    theme_context_mode: str = 'full',
) -> tuple[SceneRun, LLMModel, str]:
    """执行一次分镜 AI 调用；返回 (SceneRun, 使用的模型行, prompt_sent)。

    theme_context_mode:
      - full：完整主题块（历史背景 + 人物设定等），无主题时附 THEME_MISSING_ADVISORY
      - appearance_only：仅从人物设定中摘录「角色长相」；无摘录时不附加主题块
      - omit：不附加任何主题块
    """
    llm = _resolve_llm_row(db, model_id)
    if not llm:
        if model_id is not None:
            raise ValueError(
                f'当前节点指定的 LLM 配置（id={model_id}）不存在或未启用。请在分镜「自定义节点」中为该节点选择可用模型，或在「LLM 配置」中启用对应条目。'
            )
        raise ValueError(
            '请先在「LLM 配置」中添加并启用至少一个模型后再使用 AI 分镜生成；未配置时不调用模型。'
        )

    resolved_theme = theme_id if theme_id is not None else scene.theme_id
    mode = (theme_context_mode or 'full').strip().lower()
    if mode == 'omit':
        theme_block = ''
    elif mode == 'appearance_only':
        theme_block = build_theme_character_appearance_block(db, resolved_theme)
    else:
        theme_block = build_theme_context_block(db, resolved_theme)
        if not (theme_block or '').strip():
            theme_block = THEME_MISSING_ADVISORY
    prompt_sent = compose_prompt_sent(theme_block=theme_block, default_text=default_text, input_text=input_text)
    if not prompt_sent.strip():
        raise ValueError('default_text 与 input_text 至少填写一项（或与主题组合后非空）')

    output, err = chat_completion_user(llm.base_url, llm.api_key or None, llm.model_name, prompt_sent)
    if err:
        raise RuntimeError(err)

    run = SceneRun(
        scene_id=scene.id,
        theme_id=resolved_theme,
        default_text=default_text or '',
        user_input_text=input_text or '',
        input_text=prompt_sent,
        output_text=output or '',
        status='done',
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run, llm, prompt_sent


def run_scene(db: Session, scene: StoryboardScene, user_input: str, model_id: int | None = None) -> SceneRun:
    """兼容旧调用：整段文案视为 default_text，无手工 input。"""
    run, _, _ = run_storyboard_ai(
        db,
        scene,
        default_text=user_input,
        input_text='',
        theme_id=scene.theme_id,
        model_id=model_id,
    )
    return run
