"""Синтетические агенты-кандидаты (PRD §9.1).

Агент с истинным уровнем θ_true отвечает верно с P = σ(θ_true − β);
с вероятностью `careless` ответ инвертируется («ошибка по невнимательности»).
Агент заявляет грейд, соответствующий своему θ_true (честное заявление —
базовый сценарий валидации; gaming-сценарии вне этой фазы).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from engine.catalog import grade_for_theta
from engine.irt import p_correct
from itembank.model import Instance


@dataclass
class SyntheticAgent:
    theta_true: float
    rng: random.Random
    careless: float = 0.05
    spec: str = "backend"
    answered: int = field(default=0, init=False)

    @property
    def grade_claimed(self) -> str:
        return grade_for_theta(self.theta_true).slug

    def effective_p(self, beta: float) -> float:
        p = p_correct(self.theta_true, beta)
        return p * (1 - self.careless) + (1 - p) * self.careless

    def roll_correct(self, beta: float) -> bool:
        return self.rng.random() < self.effective_p(beta)

    def answer(self, instance: Instance) -> tuple[Any, bool]:
        """Ответ на экземпляр: (answer, intended_correct)."""
        self.answered += 1
        if self.roll_correct(instance.beta):
            return instance.reference, True
        return self._wrong_answer(instance), False

    def elapsed_ms(self, kind: str) -> int:
        """Правдоподобное время ответа (сигнал в валидацию, в скоринг не идёт)."""
        base = 35_000 if kind == "mcq" else 120_000
        return int(self.rng.lognormvariate(0, 0.5) * base)

    def _wrong_answer(self, instance: Instance) -> Any:
        if instance.kind == "mcq":
            wrong = [o for o in instance.payload["options"] if o != instance.reference]
            return self.rng.choice(wrong)
        return _wrong_sql(instance, self.rng)


def _wrong_sql(instance: Instance, rng: random.Random) -> str:
    """Заведомо неверный SQL: мутации эталона, в крайнем случае — пустой запрос
    (эталон непустой гарантируется фабрикой)."""
    ref = str(instance.reference)
    candidates = [
        ref.replace(">=", "<", 1),
        ref.replace(">", "<=", 1) if ">" in ref else ref.replace("<", ">=", 1),
        f"SELECT * FROM ({ref}) WHERE 1 = 0",
    ]
    rng.shuffle(candidates)
    for cand in candidates:
        if cand and cand != ref and not instance.check(cand):
            return cand
    return "SELECT 1 WHERE 0"
