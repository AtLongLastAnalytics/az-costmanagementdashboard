"""Configuration for the weekly report function."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportSettings(BaseSettings):
    """Report settings, populated from REPORT_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="REPORT_")

    key_vault_uri: str
    recipient: str
    budget: float | None = None
    acs_conn_secret: str = "acs-connection-string"  # noqa: S105
    acs_sender_secret: str = "acs-sender-address"  # noqa: S105
