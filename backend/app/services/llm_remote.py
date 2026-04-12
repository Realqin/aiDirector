import json
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app.core.config import settings


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip('/')


def models_list_url(base_url: str) -> str:
    base = _normalize_base_url(base_url)
    if base.endswith('/v1'):
        return f'{base}/models'
    return f'{base}/v1/models'


def chat_completions_url(base_url: str) -> str:
    base = _normalize_base_url(base_url)
    if base.endswith('/v1'):
        return f'{base}/chat/completions'
    return f'{base}/v1/chat/completions'


def _request_json(method: str, url: str, api_key: str | None, body: dict | None = None, timeout: int = 30) -> dict:
    headers: dict[str, str] = {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if api_key and api_key.strip():
        headers['Authorization'] = f'Bearer {api_key.strip()}'
    data_bytes = None
    if body is not None:
        data_bytes = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode('utf-8'))


def fetch_remote_model_ids(base_url: str, api_key: str | None = None) -> tuple[list[str], str | None]:
    parsed = urlparse(_normalize_base_url(base_url))
    if not parsed.scheme or not parsed.netloc:
        return [], '地址格式无效，需包含协议，例如 https://api.openai.com/v1'
    url = models_list_url(base_url)
    try:
        payload = _request_json('GET', url, api_key)
    except urllib.error.HTTPError as e:
        return [], f'拉取模型列表失败（HTTP {e.code}）'
    except urllib.error.URLError as e:
        return [], f'无法连接：{e.reason}'
    except Exception as e:
        return [], str(e)
    raw_data = payload.get('data')
    if not isinstance(raw_data, list):
        return [], '响应格式不符合 OpenAI 兼容接口（缺少 data 数组）'
    ids: list[str] = []
    for item in raw_data:
        if isinstance(item, dict) and item.get('id'):
            ids.append(str(item['id']))
    ids.sort()
    return ids, None


def chat_completion_user(
    base_url: str,
    api_key: str | None,
    model_name: str,
    user_content: str,
    *,
    system_content: str | None = None,
    timeout: int | None = None,
    max_tokens: int | None = None,
) -> tuple[str | None, str | None]:
    """OpenAI 兼容 POST /v1/chat/completions，返回助手文本或错误信息。"""
    if not model_name or not str(model_name).strip():
        return None, '模型标识为空'
    if not user_content or not str(user_content).strip():
        return None, '提示内容为空'
    if timeout is None:
        timeout = settings.llm_chat_timeout_seconds
    mt = settings.llm_max_tokens if max_tokens is None else max_tokens
    url = chat_completions_url(base_url)
    messages: list[dict[str, str]] = []
    if system_content and str(system_content).strip():
        messages.append({'role': 'system', 'content': str(system_content).strip()})
    messages.append({'role': 'user', 'content': str(user_content).strip()})
    body = {
        'model': str(model_name).strip(),
        'messages': messages,
        'max_tokens': mt,
        'temperature': 0.7,
    }
    try:
        payload = _request_json('POST', url, api_key, body=body, timeout=timeout)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8', errors='replace')
        except Exception:
            err_body = ''
        hint = ''
        if e.code in (401, 403) or 'invalid_api_key' in err_body or 'Incorrect API key' in err_body:
            hint = '（请检查 LLM 配置中的 Key 是否有效，或换用已启用且密钥正确的模型）'
        return None, f'模型接口错误（HTTP {e.code}）：{err_body[:500]}{hint}'
    except urllib.error.URLError as e:
        return None, f'无法连接模型服务：{e.reason}'
    except Exception as e:
        return None, str(e)
    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices:
        return None, '响应中无 choices'
    msg = choices[0].get('message') if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        return None, '响应格式异常'
    content = msg.get('content')
    if content is None:
        return None, '模型未返回文本内容'
    return str(content).strip(), None


def test_connection(base_url: str, api_key: str | None, model_name: str | None = None) -> tuple[bool, str]:
    if model_name and model_name.strip():
        url = chat_completions_url(base_url)
        body = {
            'model': model_name.strip(),
            'messages': [{'role': 'user', 'content': 'ping'}],
            'max_tokens': 5,
        }
        try:
            _request_json('POST', url, api_key, body=body, timeout=45)
            return True, '连通性测试成功（已发起对话请求）'
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8', errors='replace')
            except Exception:
                err_body = ''
            return False, f'对话请求失败（HTTP {e.code}）：{err_body[:200]}'
        except urllib.error.URLError as e:
            return False, f'无法连接：{e.reason}'
        except Exception as e:
            return False, str(e)
    ids, err = fetch_remote_model_ids(base_url, api_key)
    if err:
        return False, err
    if not ids:
        return False, '地址可访问，但未返回任何模型'
    return True, f'连通性成功，已获取 {len(ids)} 个模型标识'
