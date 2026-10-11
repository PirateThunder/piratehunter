"""Настройки core-api через pydantic-settings (префикс CORE_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORE_", env_file=".env", extra="ignore")

    # local — разработка (docs включены); stage/prod — docs выключены
    env: str = "local"
    # compose передаёт postgresql+asyncpg://...@pg-core:5432/ph_core;
    # дефолт — sqlite для локального запуска без PG
    database_url: str = "sqlite+aiosqlite:///./hunter_core_local.db"
    # если не задан — internal-заголовок не проверяется (dev-режим)
    internal_token: str | None = None
    # стартовый банк из фабрик (PRD §6: глубокие специализации — backend/frontend/qa)
    bank_specs: str = "backend,frontend,qa"
    bank_mcq_per_spec: int = 9
    bank_sql_per_spec: int = 6
    bank_seed: int = 1

    @property
    def bank_spec_list(self) -> list[str]:
        return [s.strip() for s in self.bank_specs.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
