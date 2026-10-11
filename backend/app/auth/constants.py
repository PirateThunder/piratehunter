"""Константы auth: cookie, OIDC state, демо-аккаунты dev-login."""

REFRESH_COOKIE = "ph_refresh"
# public: импортируют роутеры, чистящие cookie (logout)
COOKIE_PATH = "/api/v1/auth"

_STATE_KEY = "fsp:state:{state}"

# фиксированные демо-аккаунты dev-login (BACK_AUTH_DEV_LOGIN=1): кандидат
# без ФСП, кандидат с привязанным ФСП ID, работодатель (PRD §10).
# fsp_id демо-кандидата должен иметь историю в сидах fsp_registry.
DEV_ACCOUNTS: dict[str, dict] = {
    "candidate": {
        "email": "demo-candidate@ph.dev",
        "role": "candidate",
        "fsp_id": None,
    },
    "candidate-fsp": {
        "email": "demo-candidate-fsp@ph.dev",
        "role": "candidate",
        # fsp_001 — богатая история в мок-реестре; вход через FSP ID
        # этой личностью попадает в тот же демо-аккаунт
        "fsp_id": "fsp_001",
    },
    "employer": {
        "email": "demo-employer@ph.dev",
        "role": "employer",
        "fsp_id": None,
    },
}


def state_key(state: str) -> str:
    return _STATE_KEY.format(state=state)
