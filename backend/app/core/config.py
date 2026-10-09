from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CivicLoop"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./civicloop.db"

    # Auth & Security
    SECRET_KEY: str = "civicloop-insecure-secret-key-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Open-Weight LLM Configuration (HARD CONSTRAINTS 1 & 2)
    # Exclusively OpenAI-compatible open-weight endpoints (vLLM, Ollama, etc.)
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama-or-vllm-key"
    LLM_AGENT_MODEL: str = "deepseek-ai/DeepSeek-V4"
    LLM_VISION_MODEL: str = "Qwen/Qwen3.6-VL"
    EMBED_MODEL: str = "BAAI/bge-m3"

    # Worker Settings
    WORKER_POLL_INTERVAL_SECONDS: int = 5
    MAX_TASK_ATTEMPTS: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
