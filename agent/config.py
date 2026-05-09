from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SocialHandles(BaseModel):
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    tiktok: Optional[str] = None


class BrandConfig(BaseModel):
    brand_name: str
    website_url: str
    social_handles: SocialHandles = SocialHandles()
    crawl_depth: int = 2
    max_images: int = 150
    min_resolution: int = 512
    output_dir: str = "outputs"

    @classmethod
    def from_file(cls, path: str | Path) -> "BrandConfig":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    request_timeout: int = 30
    request_delay_ms: int = 800
    max_concurrent_requests: int = 4
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    log_level: str = "INFO"


settings = AppSettings()
