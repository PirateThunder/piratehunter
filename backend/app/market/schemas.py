"""Схемы рыночной аналитики вилок (§7.5.5)."""

from pydantic import BaseModel


class SalaryStatsOut(BaseModel):
    """«Вилка vs рынок по категории»: перцентили (p25/p50/p75) границ
    ЗП-вилок по данным платформы в категории spec×grade + размер
    категории из core. Перцентили None — пустая выборка."""

    spec: str
    grade: str
    # кандидатов в категории по данным core (None — core недоступен)
    category_size: int | None
    sample_needs: int  # потребностей в выборке
    sample_invitations: int  # приглашений в выборке
    from_p25: float | None
    from_p50: float | None
    from_p75: float | None
    to_p25: float | None
    to_p50: float | None
    to_p75: float | None
