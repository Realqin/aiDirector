"""将提示词正文与「返回格式 + 格式示例」拼接为发给模型的完整 system/user 前缀。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import PromptTemplate

_FORMAT_INTRO: dict[str, str] = {
    'json': (
        '【输出格式】只输出一段合法 JSON（禁止 markdown 代码块、禁止 JSON 前后的说明文字）。'
        '结构必须与下方「格式示例」的键名与层次完全一致；字符串内双引号须转义为 \\" 。'
    ),
    'markdown': '【输出格式】使用 Markdown；标题层级、列表等请与下方「格式示例」保持一致。',
    'text': '【输出格式】输出纯文本；分段与语气可参考下方「格式示例」（示例仅为结构参考，正文由你根据任务生成）。',
}


def normalize_response_format(value: str | None) -> str:
    v = (value or 'text').strip().lower()
    return v if v in _FORMAT_INTRO else 'text'


def compose_prompt_template_body(row: PromptTemplate | None) -> str:
    """正文（content）与格式约定分离存储，调用模型前在此拼接。"""
    if row is None:
        return ''
    main = (row.content or '').strip()
    fmt = normalize_response_format(getattr(row, 'response_format', None))
    example = (getattr(row, 'format_example', None) or '').strip()
    parts: list[str] = []
    if main:
        parts.append(main)
    intro = _FORMAT_INTRO[fmt]
    if example:
        parts.append(f'{intro}\n{example}')
    elif fmt != 'text':
        parts.append(f'{intro}\n（未配置格式示例时仍须严格遵守 {fmt} 格式输出。）')
    return '\n\n'.join(parts).strip()
