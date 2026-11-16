"""Load settings from the environment / .env without ever echoing values."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

_FIELDS = {
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "deepseek_base_url": "DEEPSEEK_BASE_URL",
    "deepseek_model": "DEEPSEEK_MODEL",
    "database_url": "DATABASE_URL",
    "ollama_url": "OLLAMA_URL",
    "embedding_model": "EMBEDDING_MODEL",
}


@dataclass(frozen=True)
class Config:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str
    ollama_url: str
    embedding_model: str

    def __repr__(self) -> str:  # never print secrets
        return "Config(<hidden>)"


def load_config(env_path: str | None = None) -> Config:
    load_dotenv(env_path or ".env", override=False)
    missing = [var for var in _FIELDS.values() if not os.environ.get(var, "").strip()]
    if missing:
        raise ValueError("missing environment variables: " + ", ".join(missing))
    return Config(**{field: os.environ[var].strip() for field, var in _FIELDS.items()})
