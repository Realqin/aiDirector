"""从模型输出中提取 JSON / 各节点结构化字段（与前端 extractJsonObjectString 等行为对齐）。"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object_string(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip().lstrip('\ufeff')
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    start = text.find('{')
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escape_next:
                escape_next = False
                continue
            if c == '\\':
                escape_next = True
                continue
            if c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    # 括号扫描失败时兜底：整段为合法 JSON 对象/数组（避免嵌套字符串边界误判导致前端无法渲染）
    t = text.strip()
    if t.startswith('{') and t.endswith('}'):
        try:
            json.loads(t)
            return t
        except (json.JSONDecodeError, TypeError):
            pass
    if t.startswith('[') and t.endswith(']'):
        try:
            json.loads(t)
            return t
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def parse_story_description(raw: str) -> tuple[bool, str]:
    """故事描述：优先从 JSON 取 story 等键（兼容旧版）；否则将整段视为纯文本。"""
    blob = extract_json_object_string(raw)
    if blob:
        try:
            o = json.loads(blob)
            if isinstance(o, dict):
                story = o.get('story') or o.get('故事') or o.get('故事梗概') or o.get('正文') or o.get('content')
                if story is not None and str(story).strip():
                    return True, str(story).strip()
        except (json.JSONDecodeError, TypeError):
            pass
    t = strip_plain_text(raw)
    if t:
        return True, t
    return False, ''


def parse_scene_decomposition(raw: str) -> tuple[bool, list[dict[str, Any]]]:
    blob = extract_json_object_string(raw)
    if not blob:
        return False, []
    try:
        o = json.loads(blob)
        if not isinstance(o, dict):
            return False, []
        lst = o.get('scenes') or o.get('场景列表') or o.get('data')
        if not isinstance(lst, list):
            return False, []
        out: list[dict[str, Any]] = []
        for i, sc in enumerate(lst):
            if not isinstance(sc, dict):
                continue
            title = sc.get('title') or sc.get('标题') or sc.get('name') or f'场景{i + 1}'
            t = sc.get('text') or sc.get('正文') or sc.get('content') or sc.get('body') or sc.get('description') or ''
            out.append({'title': str(title), 'text': str(t)})
        return (len(out) > 0), out
    except (json.JSONDecodeError, TypeError):
        return False, []


def _scene_review_original_str(v: Any) -> str:
    if v is None:
        return ''
    if isinstance(v, dict):
        try:
            return json.dumps(v, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(v)
    return str(v).strip()


def _normalize_scene_review_card(sc: Any, i: int) -> dict[str, str] | None:
    if not isinstance(sc, dict):
        return None
    title = str(sc.get('title') or sc.get('标题') or sc.get('name') or f'场景{i + 1}').strip() or f'场景{i + 1}'
    t = (
        sc.get('text')
        or sc.get('正文')
        or sc.get('content')
        or sc.get('body')
        or sc.get('description')
        or sc.get('描述')
        or ''
    )
    return {'title': title, 'text': str(t)}


def _parse_scene_review_revised_field(revised_raw: Any) -> tuple[str, list[dict[str, str]]]:
    """「修改后」必须是对象，且含非空 scenes（或 场景列表）数组；否则解析失败。"""
    if not isinstance(revised_raw, dict):
        return '', []
    lst = revised_raw.get('scenes') or revised_raw.get('场景列表')
    if not isinstance(lst, list) or not lst:
        return '', []
    out: list[dict[str, str]] = []
    for i, sc in enumerate(lst):
        n = _normalize_scene_review_card(sc, i)
        if n:
            out.append(n)
    if not out:
        return '', []
    return json.dumps({'scenes': out}, ensure_ascii=False), out


def _normalize_scene_review_issue_item(row: Any, i: int) -> dict[str, str] | None:
    """问题清单项：场景标签 + 问题描述 + 修改建议（中英键名兼容）。"""
    if not isinstance(row, dict):
        return None
    scene = str(
        row.get('场景')
        or row.get('scene')
        or row.get('场景标签')
        or row.get('scene_label')
        or '',
    ).strip()
    if not scene:
        scene = f'场景{i + 1}'
    problem = str(
        row.get('问题')
        or row.get('具体问题')
        or row.get('具体问题描述')
        or row.get('problem')
        or row.get('描述')
        or '',
    ).strip()
    suggestion = str(
        row.get('修改建议')
        or row.get('建议')
        or row.get('suggestion')
        or '',
    ).strip()
    if not problem and not suggestion:
        return None
    return {'scene': scene, 'problem': problem, 'suggestion': suggestion}


def _coerce_issue_checklist_raw(raw: Any) -> list[Any]:
    """
    模型常把「问题清单及修改建议」写成：
    - 数组：[{ "场景1": [ {...} ] }, …]（规范）
    - 对象：{ "场景1": [ … ], "场景2": [ … ] }（无外层数组）
    - 字符串：内层再 json.loads
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed: Any = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return []
        return _coerce_issue_checklist_raw(parsed)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        blocks: list[Any] = []
        for k, v in raw.items():
            if isinstance(v, list):
                blocks.append({str(k): v})
        return blocks
    return []


def _parse_nested_issue_checklist(raw: list[Any]) -> list[dict[str, str]]:
    """
    嵌套结构（常用于画面评审）：[
      { "场景1": [ { "画面1问题": "…", "修改建议": "…" }, … ] },
      { "场景2": [ … ] },
    ]
    每条画面问题展平为一条 issue_items（scene=场景键名，problem=各「*问题」键拼成多行）。
    """
    out: list[dict[str, str]] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        for scene_key, arr in block.items():
            sk = str(scene_key).strip()
            if not sk or not isinstance(arr, list):
                continue
            for shot in arr:
                if not isinstance(shot, dict):
                    continue
                sug = str(shot.get('修改建议') or shot.get('suggestion') or '').strip()
                parts: list[str] = []
                for k, v in shot.items():
                    if str(k) in ('修改建议', 'suggestion'):
                        continue
                    vv = str(v).strip() if v is not None else ''
                    kk = str(k).strip()
                    if vv:
                        parts.append(f'{kk}：{vv}' if kk else vv)
                prob = '\n'.join(parts)
                if prob or sug:
                    out.append({'scene': sk, 'problem': prob, 'suggestion': sug})
    return out


def _row_looks_like_nested_scene_issue_block(row: Any) -> bool:
    """形如 { "场景1": [ {...}, ... ] }：对象内每个值均为数组。"""
    if not isinstance(row, dict) or not row:
        return False
    for v in row.values():
        if not isinstance(v, list):
            return False
    return True


def _parse_scene_review_issue_checklist(o: dict[str, Any]) -> list[dict[str, str]]:
    raw = (
        o.get('问题清单及修改建议')
        or o.get('issue_items')
        or o.get('问题清单')
        or o.get('issues_detail')
    )
    raw = _coerce_issue_checklist_raw(raw)
    if not raw:
        return []
    out: list[dict[str, str]] = []
    out.extend(_parse_nested_issue_checklist(raw))
    for i, row in enumerate(raw):
        if _row_looks_like_nested_scene_issue_block(row):
            continue
        n = _normalize_scene_review_issue_item(row, i)
        if n:
            out.append(n)
    return out


def _issues_flat_from_checklist(items: list[dict[str, str]]) -> list[str]:
    """与旧版 issues 字符串数组对齐：每项拆成两行（问题行 + 建议行）。"""
    lines: list[str] = []
    for it in items:
        sc = str(it.get('scene') or '').strip()
        pr = str(it.get('problem') or '').strip()
        sg = str(it.get('suggestion') or '').strip()
        if pr:
            lines.append(f'{sc}：{pr}' if sc else pr)
        elif sg and sc:
            lines.append(f'{sc}：（见下方修改建议）')
        elif sg:
            lines.append('（见下方修改建议）')
        if sg:
            lines.append(f'修改建议：{sg}')
    return lines


def parse_scene_review(raw: str) -> tuple[bool, dict[str, Any]]:
    blob = extract_json_object_string(raw)
    if not blob:
        return False, {}
    try:
        o = json.loads(blob)
        if not isinstance(o, dict):
            return False, {}
        o = _unwrap_nested_review(o)
        conclusion = str(o.get('评审结论') or o.get('conclusion') or '').strip()
        issue_items = _parse_scene_review_issue_checklist(o)
        issues = o.get('问题点') or o.get('issues')
        if issues is None:
            issues = []
        if not isinstance(issues, list):
            issues = [str(issues)] if issues else []
        issues = [str(x) for x in issues]
        if issue_items:
            issues = _issues_flat_from_checklist(issue_items)
        original = _scene_review_original_str(
            o.get('原内容') or o.get('original') or o.get('before') or o.get('待评审内容') or o.get('上游内容'),
        )
        revised_raw = o.get('修改后') or o.get('revised') or o.get('after')
        revised_str, revised_scenes = _parse_scene_review_revised_field(revised_raw)
        if not revised_scenes:
            return False, {}
        return True, {
            'conclusion': conclusion,
            'issues': issues,
            'issue_items': issue_items,
            'original': original.strip(),
            'revised': revised_str.strip(),
            'revised_scenes': revised_scenes,
        }
    except (json.JSONDecodeError, TypeError):
        return False, {}


def _unwrap_nested_review(o: dict[str, Any]) -> dict[str, Any]:
    if isinstance(o, list) and o and isinstance(o[0], dict):
        return o[0]
    for k in ('data', 'result', 'payload', 'review', 'output', 'body'):
        inner = o.get(k)
        if isinstance(inner, dict) and not isinstance(inner, list):
            if any(
                x in inner
                for x in (
                    '评审结论',
                    '原内容',
                    '问题点',
                    '问题清单及修改建议',
                    '修改后',
                    'conclusion',
                    'original',
                    'revised',
                    'issues',
                    'issue_items',
                )
            ):
                return inner
    return o


def _normalize_frame_item(f: Any, si: int, fi: int) -> dict[str, str]:
    if isinstance(f, str):
        return {'description': f.strip()}
    if not isinstance(f, dict):
        return {'description': ''}
    d = (
        f.get('description')
        or f.get('描述')
        or f.get('画面描述')
        or f.get('镜头描述')
        or f.get('desc')
        or f.get('text')
        or ''
    )
    return {'description': str(d).strip()}


def _normalize_frame_scene(raw: dict[str, Any], si: int) -> dict[str, Any] | None:
    title = raw.get('title') or raw.get('标题') or raw.get('name') or f'场景{si + 1}'
    fr = raw.get('frames') or raw.get('画面') or raw.get('shots') or raw.get('画面列表')
    if not isinstance(fr, list):
        fr = []
    frames = [_normalize_frame_item(x, si, fi) for fi, x in enumerate(fr)]
    return {'title': str(title), 'frames': frames}


def parse_frame_decomposition(raw: str) -> tuple[bool, list[dict[str, Any]]]:
    blob = extract_json_object_string(raw)
    if not blob:
        return False, []
    try:
        o = json.loads(blob)
        if not isinstance(o, dict):
            return False, []
        lst = o.get('scenes') or o.get('场景列表') or o.get('data')
        if not isinstance(lst, list):
            return False, []
        out: list[dict[str, Any]] = []
        for si, sc in enumerate(lst):
            if isinstance(sc, dict):
                norm = _normalize_frame_scene(sc, si)
                if norm:
                    out.append(norm)
        return (len(out) > 0), out
    except (json.JSONDecodeError, TypeError):
        return False, []


def _unwrap_nested_frame_review(o: dict[str, Any]) -> dict[str, Any]:
    for k in ('data', 'result', 'payload', 'review', 'output', 'body'):
        inner = o.get(k)
        if isinstance(inner, dict) and not isinstance(inner, list):
            if any(
                x in inner
                for x in (
                    '总评',
                    '评审结论',
                    'conclusion',
                    'summary',
                    '优化分镜',
                    '修改后',
                    'modified',
                    'final',
                    '问题清单及修改建议',
                    '原内容',
                    '优点',
                    '改进建议',
                )
            ):
                return inner
    return o


def _optimized_scenes_from_frame_review_modified(modified: Any) -> list[dict[str, Any]]:
    """画面评审「修改后」：与画面分解同构，scenes[].title + frames[].description。

    兼容：整段 JSON 字符串；直接 scenes 数组；仅含 scenes/场景列表 的对象。
    """
    if modified is None:
        return []
    if isinstance(modified, str):
        s = modified.strip()
        if not s:
            return []
        try:
            modified = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return []
    # 模型偶发把「修改后」写成 scenes 数组而非 { "scenes": [...] }
    if isinstance(modified, list):
        out: list[dict[str, Any]] = []
        for si, sc in enumerate(modified):
            if isinstance(sc, dict):
                norm = _normalize_frame_scene(sc, si)
                if norm:
                    out.append(norm)
        return out
    if not isinstance(modified, dict):
        return []
    lst = modified.get('scenes') or modified.get('场景列表')
    if not isinstance(lst, list) or not lst:
        return []
    out2: list[dict[str, Any]] = []
    for si, sc in enumerate(lst):
        if isinstance(sc, dict):
            norm = _normalize_frame_scene(sc, si)
            if norm:
                out2.append(norm)
    return out2


def parse_frame_review(raw: str) -> tuple[bool, dict[str, Any]]:
    blob = extract_json_object_string(raw)
    if not blob:
        return False, {}
    try:
        o = json.loads(blob)
        if not isinstance(o, dict):
            return False, {}
        o = _unwrap_nested_frame_review(o)
        summary = str(
            o.get('评审结论') or o.get('总评') or o.get('summary') or o.get('conclusion') or '',
        ).strip()
        issue_items = _parse_scene_review_issue_checklist(o)
        original = _scene_review_original_str(
            o.get('原内容')
            or o.get('original')
            or o.get('before')
            or o.get('待评审分镜')
            or o.get('上游内容'),
        )
        merits = o.get('优点') or o.get('merits')
        if merits is None:
            merits = []
        if not isinstance(merits, list):
            merits = [str(merits)] if merits else []
        merits = [str(x) for x in merits]
        suggestions = o.get('改进建议') or o.get('suggestions') or o.get('改进点')
        if suggestions is None:
            suggestions = []
        if not isinstance(suggestions, list):
            suggestions = [str(suggestions)] if suggestions else []
        suggestions = [str(x) for x in suggestions]
        scenes_out: list[dict[str, Any]] = []
        revised_raw = (
            o.get('修改后')
            or o.get('revised')
            or o.get('after')
            or o.get('modified')
            or o.get('final')
        )
        scenes_out = _optimized_scenes_from_frame_review_modified(revised_raw)
        if not scenes_out:
            opt = (
                o.get('优化分镜')
                or o.get('optimizedScenes')
                or o.get('framesReview')
                or o.get('optimized_scenes')
            )
            scenes_out = _optimized_scenes_from_frame_review_modified(opt)
        if not scenes_out:
            # 少数模型把优化结果放在根上
            scenes_out = _optimized_scenes_from_frame_review_modified(
                o.get('scenes') or o.get('场景列表'),
            )
        orig_stripped = original.strip()
        if (
            not summary
            and not merits
            and not suggestions
            and not scenes_out
            and not issue_items
            and not orig_stripped
        ):
            return False, {}
        return True, {
            'summary': summary,
            'merits': merits,
            'suggestions': suggestions,
            'optimized_scenes': scenes_out,
            'issue_items': issue_items,
            'original': orig_stripped,
        }
    except (json.JSONDecodeError, TypeError):
        return False, {}


def parse_single_frame_description(raw: str) -> tuple[bool, str]:
    blob = extract_json_object_string(raw)
    if blob:
        try:
            o = json.loads(blob)
            if isinstance(o, dict):
                d = o.get('description') or o.get('描述') or o.get('text') or o.get('content')
                if isinstance(d, str) and d.strip():
                    return True, d.strip()
        except (json.JSONDecodeError, TypeError):
            pass
    t = raw.strip()
    fence = re.match(r'^```(?:\w+)?\s*([\s\S]*?)```', t, re.MULTILINE)
    if fence:
        t = fence.group(1).strip()
    if t and not t.lstrip().startswith('{'):
        return True, t.strip()
    return False, ''


def strip_plain_text(raw: str) -> str:
    """完整内容「单格」接口：模型应返回一条纯文本提示词；可剥最外层 markdown 围栏与弯引号。"""
    t = (raw or '').strip()
    m = re.match(r'^```(?:\w+)?\s*([\s\S]*?)```', t, re.MULTILINE)
    if m:
        t = m.group(1).strip()
    return t.strip().strip('"\u201c\u201d')
