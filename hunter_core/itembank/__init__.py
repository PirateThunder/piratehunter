"""Банк заданий hunter_core: модель, реестр, фабрики шаблонов.

Импорт пакета регистрирует билдеры фабрик в registry.FACTORY_BUILDERS,
поэтому BankRegistry.from_json работает после `import itembank`.
"""

from itembank import factory_mcq, factory_sql  # noqa: F401 — side effect: register_factory
from itembank.model import TIME_LIMITS, Instance, ItemGenerationError, ItemTemplate
from itembank.registry import BankRegistry, SanityReport, sanity_check_template

__all__ = [
    "TIME_LIMITS",
    "BankRegistry",
    "Instance",
    "ItemGenerationError",
    "ItemTemplate",
    "SanityReport",
    "sanity_check_template",
]
