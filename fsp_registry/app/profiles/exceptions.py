"""404 «нет истории ФСП» — обязательный кейс ТЗ (PRD §7.9), не ошибка движка."""

from fastapi import Request, status
from fastapi.responses import JSONResponse


class ProfileNotFoundError(Exception):
    def __init__(self, fsp_id: str) -> None:
        self.fsp_id = fsp_id
        super().__init__(fsp_id)


async def profile_not_found_handler(
    request: Request, exc: ProfileNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"no FSP history for fsp_id={exc.fsp_id}"},
    )
