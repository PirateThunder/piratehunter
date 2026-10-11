"""Общие базы: ORM Base с конвенцией имён, переносимые типы колонок."""

from datetime import UTC, datetime

from sqlalchemy import JSON, MetaData, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


# JSONB в postgres, JSON в sqlite (тесты): метаданные остаются переносимыми
JSONBVariant = JSONB().with_variant(JSON(), "sqlite")

# text[] в postgres, JSON-список строк в sqlite (тесты)
StringArray = ARRAY(String).with_variant(JSON(), "sqlite")


def utcnow() -> datetime:
    """Naive UTC (колонки DateTime без tz — дизайн как у piratepitch).
    Python-side default/onupdate: значение известно ORM сразу, без
    рефетча серверного выражения после UPDATE (async-совместимо)."""
    return datetime.now(UTC).replace(tzinfo=None)


def import_models() -> None:
    """Импорт всех ORM-моделей одним вызовом (для alembic env и тестов)."""
    from .candidates import models as _candidates  # noqa: F401
    from .companies import models as _companies  # noqa: F401
    from .invitations import models as _invitations  # noqa: F401
    from .needs import models as _needs  # noqa: F401
    from .users import models as _users  # noqa: F401
