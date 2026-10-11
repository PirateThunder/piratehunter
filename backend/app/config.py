"""Глобальные настройки бэкенда: env-переменные с префиксом BACK_."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BACK_")

    env: str = "local"  # local|staging|prod — /docs виден только в local
    port: int = 64844

    database_url: str = (
        "postgresql+asyncpg://ph:ph@localhost:55432/ph_back"
    )
    redis_url: str = "redis://localhost:56379/0"

    # core-api (hunter_core, единственная точка связи — HTTP, internal)
    core_api_url: str = "http://localhost:51457"
    # fsp_registry (мок-реестр достижений + мок-OIDC «FSP ID», internal)
    fsp_registry_url: str = "http://localhost:52457"
    # публичный (browser-facing) базовый URL реестра — только для
    # authorize_url, куда ведём браузер; server-side вызовы идут на
    # fsp_registry_url внутри docker-сети
    fsp_public_url: str = "http://localhost:52457"
    fsp_client_id: str = "piratehunter-backend"
    fsp_client_secret: str | None = None
    # redirect_uri флоу FSP ID — GET-callback backend'а на origin ФРОНТА
    # (Next проксирует /api/* в backend), чтобы refresh-cookie ставилась
    # на домен фронта
    fsp_redirect_uri: str = "http://localhost:56151/api/v1/auth/fsp/callback"
    # origin фронта — финальный редирект после FSP-входа
    front_url: str = "http://localhost:56151"
    fsp_state_ttl: int = 600  # сек жизни OIDC state в Redis
    fsp_profile_cache_ttl: int = 3600  # сек кэша достижений в Redis

    # сессионная авторизация: JWT HS256; dev-login — только для локальной
    # разработки (BACK_AUTH_DEV_LOGIN=1, в проде выключен!)
    jwt_secret: str | None = None
    auth_dev_login: bool = False
    # csv список Origin'ов фронта
    cors_origins: str = "http://localhost:56151"

    # вход по коду из письма: SMTP для отправки; без smtp_host код
    # пишется в лог и (в env=local) возвращается в dev_code ответа
    smtp_host: str | None = None
    smtp_port: int = 465  # 465 = SSL, 587 = STARTTLS
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None  # None → smtp_user
    email_code_ttl: int = 600  # сек жизни кода
    email_code_cooldown: int = 60  # сек между запросами кода на адрес
    email_code_max_attempts: int = 5  # попыток ввода до сброса кода
    email_code_daily_per_email: int = 10  # кодов в сутки на адрес
    email_code_daily_per_ip: int = 30  # запросов в сутки с IP

    # лимит создания приглашений (NFR §12): штук в час на компанию
    invitation_rate_per_hour: int = 100

    # кулдауны грейдов (§7.4.3, сроки — наш выбор, в конфиге)
    grade_change_cooldown_days: int = 90  # смена подтверждённого грейда
    retest_cooldown_days: int = 30  # повтор теста на текущий грейд

    catalog_cache_ttl: int = 300  # сек кэша справочника core в памяти

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @field_validator(
        "jwt_secret",
        "fsp_client_secret",
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        # docker-compose подставляет пустую строку, если env не задан
        return None if v == "" else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
