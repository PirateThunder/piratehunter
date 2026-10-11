"""Ошибки в формате OAuth 2.0 (RFC 6749 §5.2): {"error", "error_description"}."""

from fastapi import Request, status
from fastapi.responses import JSONResponse


class OAuthError(Exception):
    def __init__(
        self,
        error: str,
        description: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")


async def oauth_error_handler(request: Request, exc: OAuthError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "error_description": exc.description},
        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
    )
