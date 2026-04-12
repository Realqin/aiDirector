import json
import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import LLMModel, PromptTemplate
from app.services.llm_remote import chat_completion_user
from app.services.prompt_compose import compose_prompt_template_body

ThemeField = Literal['historical_background', 'description']

_ERR_THEME_PROMPT_REQUIRED = (
    '请先在「提示词管理」中准备主题用提示词模板，并在主题弹窗「配置」里为该槽位选择该模板；'
    '未选择提示词时不调用模型（禁止使用内置默认指令）。'
)
_ERR_THEME_PROMPT_EMPTY = '所选提示词模板不存在或拼接后正文为空，请先在「提示词管理」中编辑该模板。'


def resolve_llm(db: Session, model_id: int | None) -> tuple[LLMModel | None, str | None]:
    if model_id is not None:
        row = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not row:
            return None, '指定的模型配置不存在，请在主题「配置」中重新选择模型'
        if not row.enabled:
            return None, '指定的模型配置已禁用，请在「LLM 配置」中启用该模型或更换为已启用的模型'
        return row, None
    row = db.query(LLMModel).filter(LLMModel.enabled.is_(True)).order_by(LLMModel.id.desc()).first()
    if not row:
        return None, '请先在「LLM 配置」中添加并启用至少一个模型；未配置时不调用主题 AI。'
    return row, None


def prompt_template_body(db: Session, prompt_template_id: int | None) -> str:
    if prompt_template_id is None:
        return ''
    row = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_template_id).first()
    return compose_prompt_template_body(row)


def _parse_theme_json(raw: str) -> dict[str, str]:
    text = (raw or '').strip()
    if not text:
        return {'name': '', 'historical_background': '', 'description': ''}
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        text = m.group(0)
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        return {'name': '', 'historical_background': '', 'description': ''}
    if not isinstance(data, dict):
        return {'name': '', 'historical_background': '', 'description': ''}

    def _s(key: str) -> str:
        v = data.get(key)
        if v is None:
            return ''
        return str(v).strip()

    return {
        'name': _s('name'),
        'historical_background': _s('historical_background') or _s('background') or _s('era'),
        'description': _s('description') or _s('desc'),
    }


def theme_ai_field(
    db: Session,
    field: ThemeField,
    *,
    model_id: int | None,
    prompt_template_id: int | None,
    theme_name: str,
    historical_background: str,
    description: str,
    extra_hint: str,
) -> tuple[str, str | None]:
    if prompt_template_id is None:
        return '', _ERR_THEME_PROMPT_REQUIRED
    llm, err = resolve_llm(db, model_id)
    if err or not llm:
        return '', err
    tmpl = prompt_template_body(db, prompt_template_id)
    if not (tmpl or '').strip():
        return '', _ERR_THEME_PROMPT_EMPTY
    system = tmpl
    user = (
        '【当前表单上下文】\n'
        f'主题名称：{theme_name or "（空）"}\n'
        f'时代背景：{historical_background or "（空）"}\n'
        f'人物设定：{description or "（空）"}\n'
        f'用户补充说明：{extra_hint.strip() or "（无，请结合已有字段自由发挥）"}\n\n'
        '请只输出你要填写到表单对应栏的正文，不要附加解释。'
    )
    out, cerr = chat_completion_user(
        llm.base_url,
        llm.api_key or None,
        llm.model_name,
        user,
        system_content=system,
    )
    if cerr:
        return '', cerr
    return (out or '').strip(), None


def theme_ai_assist(
    db: Session,
    user_hint: str,
    *,
    model_id: int | None = None,
    prompt_template_id: int | None = None,
) -> tuple[dict[str, str], str | None]:
    if prompt_template_id is None:
        return {}, _ERR_THEME_PROMPT_REQUIRED
    llm, err = resolve_llm(db, model_id)
    if err or not llm:
        return {}, err
    tmpl = prompt_template_body(db, prompt_template_id)
    if not (tmpl or '').strip():
        return {}, _ERR_THEME_PROMPT_EMPTY
    system = tmpl
    user = (
        '用户希望为短视频创作定义一个「主题」。用户说明如下：\n'
        f'{user_hint.strip()}\n\n'
        '请输出严格 JSON（不要 markdown 代码块），格式：'
        '{"name":"","historical_background":"","description":""}。\n'
        'name 为简短主题名；historical_background 为时代/社会背景设定（一两句）；'
        'description 键填写「人物设定」：主要角色、关系、性格与视觉气质等（2-5 句，勿与历史背景重复堆砌）。'
        '无法推断的字段用空字符串。'
    )
    out, cerr = chat_completion_user(
        llm.base_url,
        llm.api_key or None,
        llm.model_name,
        user,
        system_content=system,
    )
    if cerr:
        return {}, cerr
    return _parse_theme_json(out or ''), None
