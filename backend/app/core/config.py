from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'aiDirector'
    app_env: str = 'dev'
    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/aidirector'
    redis_url: str = 'redis://localhost:6379/0'
    api_prefix: str = '/api/v1'

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


settings = Settings()
