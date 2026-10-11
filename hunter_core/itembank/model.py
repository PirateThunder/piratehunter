"""Модель банка заданий: шаблоны и экземпляры (PRD §7.4.1).

Задание = шаблон + seed. ItemTemplate задаёт семейство задач фиксированной
сложности (β) и несёт генератор уникальных экземпляров; Instance — готовое
задание с текстом, payload (варианты / SQL-схема), эталоном и чекером.
Callable-части шаблона не сериализуются: реестр восстанавливает генератор
по factory_id + params (см. itembank/registry.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Таймлимиты на вопрос (PRD §7.4.2): против гугления/списывания.
TIME_LIMITS: dict[str, int] = {"mcq": 90, "sql": 240}

ITEM_KINDS = tuple(TIME_LIMITS)


class ItemGenerationError(RuntimeError):
    """Шаблон не смог сгенерировать валидный экземпляр по seed."""


@dataclass
class Instance:
    """Конкретный экземпляр задания (шаблон × seed)."""

    template_id: str
    seed: int
    kind: str  # mcq | sql
    topic: str
    beta: float
    question_text: str
    payload: dict[str, Any]  # mcq: {code, options}; sql: {setup_sql, schema, columns}
    reference: Any  # mcq: текст верного варианта; sql: эталонный запрос
    checker: Any = field(repr=False)  # Callable[[Any], bool]
    time_limit_s: int = 90

    def check(self, answer: Any) -> bool:
        try:
            return bool(self.checker(answer))
        except Exception:
            return False


@dataclass
class ItemTemplate:
    """Параметризованный шаблон задания.

    params — JSON-сериализуемая структура (семейство + фиксированные слоты);
    instantiate(seed) варьирует литералы и восстанавливается из params
    билдерами фабрик при загрузке банка.
    """

    id: str
    spec: str
    topic: str
    grade_band: str
    kind: str  # mcq | sql
    beta: float
    factory_id: str
    params: dict[str, Any]
    version: int = 1
    active: bool = True
    instantiate: Any = field(default=None, repr=False)  # Callable[[int], Instance]

    def make(self, seed: int) -> Instance:
        if self.instantiate is None:
            raise ItemGenerationError(
                f"шаблон {self.id}: генератор не привязан (загрузите через BankRegistry)"
            )
        return self.instantiate(seed)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "spec": self.spec,
            "topic": self.topic,
            "grade_band": self.grade_band,
            "kind": self.kind,
            "beta": self.beta,
            "factory_id": self.factory_id,
            "params": self.params,
            "version": self.version,
            "active": self.active,
        }

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> ItemTemplate:
        return cls(
            id=rec["id"],
            spec=rec["spec"],
            topic=rec["topic"],
            grade_band=rec["grade_band"],
            kind=rec["kind"],
            beta=float(rec["beta"]),
            factory_id=rec["factory_id"],
            params=dict(rec["params"]),
            version=int(rec.get("version", 1)),
            active=bool(rec.get("active", True)),
        )
