"""Configuration loading: env vars (pydantic-settings) + YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
OUT_DIR = PROJECT_ROOT / "out"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATE_DB_PATH = PROJECT_ROOT / "state.sqlite"


class Settings(BaseSettings):
    """Environment-backed runtime settings."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_backend: Literal["local", "copilot"] = "local"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct-q4_K_M"

    copilot_endpoint: str = ""
    copilot_api_key: str = ""
    copilot_deployment: str = "gpt-4o-mini"
    copilot_api_version: str = "2024-06-01"

    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    max_items: int = 12
    since_days: int = 7
    ranking_use_embeddings: bool = False

    ca_bundle: str = ""
    insecure_ssl: bool = False


class SourceConfig(BaseModel):
    name: str
    kind: Literal["rss", "html"]
    url: str
    section: str = ""
    enabled: bool = True
    weight: float = 1.0


class TopicConfig(BaseModel):
    name: str
    weight: float = 1.0
    keywords: list[str] = Field(default_factory=list)
    phrases: list[str] = Field(default_factory=list)
    seed_sentences: list[str] = Field(default_factory=list)


class PenaltyConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    weight: float = 0.5


class TopicsFile(BaseModel):
    topics: list[TopicConfig] = Field(default_factory=list)
    penalties: PenaltyConfig = Field(default_factory=PenaltyConfig)


class PromptsFile(BaseModel):
    system: str
    user: str


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML file {path} must contain a mapping at the top level.")
    return data


def load_sources(path: Path | None = None) -> list[SourceConfig]:
    path = path or (CONFIG_DIR / "sources.yaml")
    data = _load_yaml(path)
    raw = data.get("sources", [])
    return [SourceConfig(**item) for item in raw]


def load_topics(path: Path | None = None) -> TopicsFile:
    path = path or (CONFIG_DIR / "topics.yaml")
    data = _load_yaml(path)
    return TopicsFile(**data)


def load_prompts(path: Path | None = None) -> PromptsFile:
    path = path or (CONFIG_DIR / "prompts.yaml")
    data = _load_yaml(path)
    return PromptsFile(**data)
