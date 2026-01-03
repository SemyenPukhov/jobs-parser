import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache
from typing import Optional

# Загружаем переменные окружения из .env файла
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True)
    
    # Environment
    ENVIRONMENT: str = "dev"

    # Database
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "jobs_parser"
    DB_HOST: str = "db"
    DB_PORT: str = "5432"

    # Slack
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_CHANNEL_ID: Optional[str] = None
    SLACK_MANAGER_ID: Optional[str] = None

    # AI Matching
    OPENROUTER_API_KEY: Optional[str] = None
    DEVELOPERS_API_URL: str = "http://103.54.16.194/api/resumes/active/freelance"
    MATCHING_THRESHOLD_HIGH: int = 70
    MATCHING_THRESHOLD_LOW: int = 50

    # PROXY
    PROXY_USER: Optional[str] = None
    PROXY_PASS: Optional[str] = None
    PROXY_HOST: Optional[str] = None

    # just remote
    JUST_REMOTE_LOGIN: Optional[str] = None
    JUST_REMOTE_PWD: Optional[str] = None

    # AmoCRM
    AMOCRM_TOKEN: Optional[str] = None
    AMOCRM_BASE_URL: str = "https://fortech.amocrm.ru"
    AMOCRM_PIPELINE_ID: int = 10355510

    # RapidAPI Y Combinator jobs
    RAPID_YCOMB_API_KEY: Optional[str] = None
    
    # RapidAPI Active Jobs DB
    RAPID_ACTIVEJOBS_API_KEY: Optional[str] = None

    # API
    API_V1_PREFIX: str = "/api"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    @field_validator('AMOCRM_PIPELINE_ID', 'MATCHING_THRESHOLD_HIGH', 'MATCHING_THRESHOLD_LOW', mode='before')
    @classmethod
    def parse_int_or_default(cls, v, info):
        if v is None or v == '':
            defaults = {
                'AMOCRM_PIPELINE_ID': 10355510,
                'MATCHING_THRESHOLD_HIGH': 70,
                'MATCHING_THRESHOLD_LOW': 50,
            }
            return defaults.get(info.field_name, 0)
        return int(v)


@lru_cache()
def get_settings() -> Settings:
    """
    Получение настроек приложения с кэшированием.
    Используется для предотвращения повторной загрузки .env файла.
    """
    return Settings()


# Создаем глобальный экземпляр настроек
settings = get_settings()
