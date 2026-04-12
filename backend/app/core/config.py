from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'aiDirector'
    app_env: str = 'dev'
    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/aidirector'
    redis_url: str = 'redis://localhost:6379/0'
    api_prefix: str = '/api/v1'
    # OpenAI 兼容对话：等待上游返回完整响应（含大 JSON）的最长时间（秒）。画面评审等节点易超过 120s。
    llm_chat_timeout_seconds: int = 300
    # 单次回复上限；完整内容批量 JSON（多场景×多画面）易超 4k，默认提高到 16k（可按供应商上限在 .env 调整）
    llm_max_tokens: int = 16384

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


settings = Settings()
