"""Реестр банка заданий: шаблоны, фильтры, версии, сериализация.

Банк сериализуется в JSON без callable-частей; при загрузке генераторы
восстанавливаются по factory_id билдерами, которые фабрики регистрируют
в FACTORY_BUILDERS при импорте (см. itembank/__init__.py).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from itembank.model import Instance, ItemTemplate

BANK_FORMAT = "hunter-bank/1"

# factory_id -> builder(template) -> instantiate(seed) -> Instance.
FACTORY_BUILDERS: dict[str, Callable[[ItemTemplate], Callable[[int], Instance]]] = {}


def register_factory(
    factory_id: str, builder: Callable[[ItemTemplate], Callable[[int], Instance]]
) -> None:
    FACTORY_BUILDERS[factory_id] = builder


@dataclass
class SanityReport:
    """Итог sanity-чека шаблона (PRD §10: 20 seeds → чекер сходится на эталоне)."""

    template_id: str
    ok: bool
    n_seeds: int
    failures: list[str] = field(default_factory=list)


class BankRegistry:
    def __init__(self, templates: Iterable[ItemTemplate] | None = None) -> None:
        self._templates: dict[str, ItemTemplate] = {}
        for t in templates or ():
            self.add(t)

    def add(self, template: ItemTemplate) -> None:
        if template.id in self._templates:
            raise ValueError(f"шаблон с id {template.id!r} уже в банке")
        self._templates[template.id] = template

    def __len__(self) -> int:
        return len(self._templates)

    def __iter__(self) -> Iterator[ItemTemplate]:
        return iter(self.filter())

    def get(self, template_id: str) -> ItemTemplate:
        try:
            return self._templates[template_id]
        except KeyError:
            raise KeyError(f"шаблон {template_id!r} не найден в банке") from None

    def filter(
        self,
        spec: str | None = None,
        kind: str | None = None,
        topic: str | None = None,
        active_only: bool = True,
        exclude: Iterable[str] = (),
    ) -> list[ItemTemplate]:
        excluded = set(exclude)
        out = []
        for t in self._templates.values():
            if active_only and not t.active:
                continue
            if spec is not None and t.spec != spec:
                continue
            if kind is not None and t.kind != kind:
                continue
            if topic is not None and t.topic != topic:
                continue
            if t.id in excluded:
                continue
            out.append(t)
        return sorted(out, key=lambda t: t.id)

    def topics(self, spec: str) -> list[str]:
        return sorted({t.topic for t in self.filter(spec=spec)})

    def deactivate(self, template_id: str) -> None:
        """Гашение скомпрометированного шаблона без остановки системы (PRD §7.4.4)."""
        self.get(template_id).active = False

    def to_json(self, path: str | Path) -> None:
        payload = {
            "format": BANK_FORMAT,
            "templates": [t.to_record() for t in self.filter(active_only=False)],
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> BankRegistry:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("format") != BANK_FORMAT:
            raise ValueError(f"неизвестный формат банка: {payload.get('format')!r}")
        reg = cls()
        for rec in payload["templates"]:
            template = ItemTemplate.from_record(rec)
            builder = FACTORY_BUILDERS.get(template.factory_id)
            if builder is None:
                raise ValueError(f"нет билдера для factory_id {template.factory_id!r}")
            template.instantiate = builder(template)
            reg.add(template)
        return reg


def sanity_check_template(template: ItemTemplate, n_seeds: int = 20) -> SanityReport:
    """Проверка шаблона: n_seeds экземпляров, чекер обязан сходиться на эталоне.

    Для mcq дополнительно: каждый дистрактор обязан НЕ проходить чекер.
    Для sql: заведомо пустой запрос обязан НЕ проходить (эталон непустой
    гарантируется фабрикой).
    """
    failures: list[str] = []
    for i in range(n_seeds):
        seed = 10_000 + i
        try:
            inst = template.make(seed)
        except Exception as e:
            failures.append(f"seed={seed}: генерация упала: {e!r}")
            continue
        if not inst.check(inst.reference):
            failures.append(f"seed={seed}: чекер не принял эталон")
            continue
        if inst.kind == "mcq":
            wrong = [o for o in inst.payload.get("options", []) if o != inst.reference]
            bad = [o for o in wrong if inst.check(o)]
            if bad:
                failures.append(f"seed={seed}: дистрактор проходит чекер: {bad[0]!r}")
            if len(set(inst.payload.get("options", []))) < 4:
                failures.append(f"seed={seed}: меньше 4 уникальных вариантов")
        elif inst.kind == "sql" and inst.check("SELECT 1 WHERE 0"):
            failures.append(f"seed={seed}: пустой запрос проходит чекер")
    return SanityReport(
        template_id=template.id, ok=not failures, n_seeds=n_seeds, failures=failures
    )
