import json
import random
import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import LLMModel, PromptTemplate
from app.services.llm_remote import chat_completion_user

_ERA_SAMPLES = [
    '盛唐长安，坊市与胡商交织，诗酒与丝路并盛。',
    '北宋汴京，勾栏瓦舍与漕运码头并立，市井烟火浓烈。',
    '明代江南市镇，手工业与书坊兴起，文人雅集与市民趣味并存。',
    '清末民初口岸城市，西风东渐，传统礼俗与新式学堂并行。',
    '二十世纪八十年代内地小城，改革初启，喇叭裤与国营厂并存。',
    '近未来东亚都市圈，人机协作日常化，旧街巷与立体交通叠合。',
]

_DESC_SAMPLES = [
    '主角在雨夜霓虹下追逐一条线索，镜头强调冷暖对比与手持呼吸感。',
    '以「一封未寄出的信」串联三代人记忆，旁白克制，留白偏多。',
    '美食短视频：一镜到底展示从菜场到上桌，突出蒸汽与油润质感。',
    '校园轻喜剧：误会—反转—和解三段式，节奏轻快，配乐偏独立流行。',
    '非遗手作纪录：特写指尖与工具磨损痕迹，穿插老师傅口述史。',
]

_DEFAULT_SYSTEM_BG = (
    '你是短视频策划助手。根据用户给出的上下文，只输出一段「时代/社会背景」设定（中文 1–3 句），'
    '不要标题、不要 JSON、不要列表符号。'
)
_DEFAULT_SYSTEM_DESC = (
    '你是短视频策划助手。根据用户给出的上下文，只输出「画面与叙事描述」（中文 2–5 句），'
    '不要标题、不要 JSON、不要列表符号。'
)

ThemeField = Literal['historical_background', 'description']


def random_theme_fill() -> dict[str, str]:
    return {
        'historical_background': random.choice(_ERA_SAMPLES),
        'description': random.choice(_DESC_SAMPLES),
    }


def random_historical_background() -> str:
    return random.choice(_ERA_SAMPLES)


def random_description() -> str:
    return random.choice(_DESC_SAMPLES)


def resolve_llm(db: Session, model_id: int | None) -> tuple[LLMModel | None, str | None]:
    if model_id is not None:
        row = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not row:
            return None, '指定的模型配置不存在'
        return row, None
    row = db.query(LLMModel).filter(LLMModel.enabled.is_(True)).order_by(LLMModel.id.desc()).first()
    if not row:
        return None, '请先在 LLM 配置中添加并启用至少一个模型，或在主题配置中指定模型'
    return row, None


def prompt_template_body(db: Session, prompt_template_id: int | None) -> str:
    if prompt_template_id is None:
        return ''
    row = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_template_id).first()
    if not row:
        return ''
    return (row.content or '').strip()


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
    llm, err = resolve_llm(db, model_id)
    if err or not llm:
        return '', err
    tmpl = prompt_template_body(db, prompt_template_id)
    system = tmpl if tmpl else (_DEFAULT_SYSTEM_BG if field == 'historical_background' else _DEFAULT_SYSTEM_DESC)
    user = (
        '【当前表单上下文】\n'
        f'主题名称：{theme_name or "（空）"}\n'
        f'时代背景：{historical_background or "（空）"}\n'
        f'描述：{description or "（空）"}\n'
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
    llm, err = resolve_llm(db, model_id)
    if err or not llm:
        return {}, err
    tmpl = prompt_template_body(db, prompt_template_id)
    system = tmpl if tmpl else None
    user = (
        '用户希望为短视频创作定义一个「主题」。用户说明如下：\n'
        f'{user_hint.strip()}\n\n'
        '请输出严格 JSON（不要 markdown 代码块），格式：'
        '{"name":"","historical_background":"","description":""}。\n'
        'name 为简短主题名；historical_background 为时代/社会背景设定（一两句）；'
        'description 为背景与画面气质的展开描述（2-5 句）。'
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
