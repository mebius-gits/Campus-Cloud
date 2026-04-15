from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    proxmox_host: str = Field(default="localhost")
    proxmox_user: str = Field(default="")
    proxmox_password: str = Field(default="")
    proxmox_verify_ssl: bool = Field(default=False)
    proxmox_api_timeout: int = Field(default=30, ge=3, le=300)

    collector_max_workers: int = Field(default=8, ge=1, le=32)
    collector_fetch_config: bool = Field(default=True)
    collector_fetch_lxc_interfaces: bool = Field(default=True)
    collector_retry_attempts: int = Field(default=3, ge=1, le=10)
    collector_retry_backoff: float = Field(default=0.3, ge=0.0, le=10.0)

    # Reuse existing template recommendation vLLM settings for now.
    vllm_base_url: str = Field(
        default="http://localhost:8000/v1",
        alias="template_recommendation_vllm_base_url",
    )
    vllm_api_key: str = Field(
        default="",
        alias="template_recommendation_vllm_api_key",
    )
    vllm_model_name: str = Field(
        default="",
        alias="template_recommendation_vllm_model_name",
    )
    chat_timeout: int = Field(default=120, ge=10, le=600)


settings = Settings()
