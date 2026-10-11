"""Настройки сервиса: env-переменные с префиксом FSPREG_.

Боевых секретов у мока нет (Q&A 06.10: «имитации достаточно»), поэтому
все значения имеют рабочие дефолты — сервис в compose стартует без env.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FSPREG_")

    env: str = "local"  # local — единственный env, где виден /docs
    port: int = 52457

    # мок-подпись HS256 для id/access токенов FSP ID; на боевом Keycloak
    # заменяется конфигом клиента, код backend не меняется (PRD §7.1)
    jwt_secret: str = "fsp-id-mock-local-secret-0123456789abcdef"
    issuer: str = "http://localhost:52457"
    # client-конфиг backend'а (единственный зарегистрированный клиент)
    oidc_client_id: str = "piratehunter-backend"
    # csv allowlist redirect_uri; пусто = не проверяем (мок, внутренняя сеть)
    oidc_allowed_redirect_uris: str = ""

    code_ttl_seconds: int = 300  # жизнь authorization code
    token_ttl_seconds: int = 3600  # жизнь access/id токенов

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _empty_to_default(cls, v: object) -> object:
        # docker-compose подставляет пустую строку, если env не задан;
        # пустая подпись невалидна для HMAC — откатываемся на дефолт
        if v == "":
            return "fsp-id-mock-local-secret-0123456789abcdef"
        return v

    @property
    def redirect_uri_allowlist(self) -> list[str]:
        return [u.strip() for u in self.oidc_allowed_redirect_uris.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
