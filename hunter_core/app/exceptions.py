"""Кастомные исключения core-api → exception handlers в main.py."""

from __future__ import annotations


class AppError(Exception):
    status_code = 500
    detail = "внутренняя ошибка core-api"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        if detail:
            self.detail = detail


class BadRequestError(AppError):
    status_code = 400
    detail = "некорректный запрос"


class UnauthorizedError(AppError):
    status_code = 401
    detail = "недействительный X-Internal-Token"


class NotFoundError(AppError):
    status_code = 404
    detail = "не найдено"


class ConflictError(AppError):
    status_code = 409
    detail = "конфликт состояния"
