import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache

# Загружаем переменные окружения из .env файла
load_dotenv()


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")

    # Database
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "jobs_parser")
    DB_HOST: str = os.getenv("DB_HOST", "db")
    DB_PORT: str = os.getenv("DB_PORT", "5432")

    # Slack
    SLACK_BOT_TOKEN: str | None = os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL_ID: str | None = os.getenv("SLACK_CHANNEL_ID")
    SLACK_MANAGER_ID: str | None = os.getenv("SLACK_MANAGER_ID")

    # AI Matching
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    DEVELOPERS_API_URL: str = os.getenv("DEVELOPERS_API_URL", "http://103.54.16.194/api/resumes/active/freelance")
    MATCHING_THRESHOLD_HIGH: int = int(os.getenv("MATCHING_THRESHOLD_HIGH", "70"))
    MATCHING_THRESHOLD_LOW: int = int(os.getenv("MATCHING_THRESHOLD_LOW", "50"))

    # PROXY
    PROXY_USER: str | None = os.getenv("PROXY_USER")
    PROXY_PASS: str | None = os.getenv("PROXY_PASS")
    PROXY_HOST: str | None = os.getenv("PROXY_HOST")

    # just remote
    JUST_REMOTE_LOGIN: str = os.getenv("JUST_REMOTE_LOGIN")
    JUST_REMOTE_PWD: str = os.getenv("JUST_REMOTE_PWD")

    # AmoCRM
    AMOCRM_TOKEN: str | None = os.getenv("AMOCRM_TOKEN")
    AMOCRM_BASE_URL: str = os.getenv("AMOCRM_BASE_URL", "https://fortech.amocrm.ru")
    AMOCRM_PIPELINE_ID: int = int(os.getenv("AMOCRM_PIPELINE_ID", "10355510"))

    # RapidAPI Y Combinator jobs
    RAPID_YCOMB_API_KEY: str | None = os.getenv("RAPID_YCOMB_API_KEY")
    # JWT
    # JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    # JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    # ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    #     os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "2400"))

    # API
    API_V1_PREFIX: str = "/api"

    # CORS
    # CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Получение настроек приложения с кэшированием.
    Используется для предотвращения повторной загрузки .env файла.
    """
    return Settings()


# Создаем глобальный экземпляр настроек
settings = get_settings()
