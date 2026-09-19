"""Configuration for the transform function."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, populated from TRANSFORM_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="TRANSFORM_")

    storage_account_url: str
    raw_container: str = "raw"
    curated_container: str = "curated"
    raw_prefix: str = "cost-exports"
    curated_prefix: str = "cost"
    watermark_blob: str = "_watermark.txt"
