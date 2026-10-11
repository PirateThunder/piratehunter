"""Модель пользователя (PRD §5.1 User + auth-идентичности).

fsp_id живёт на уровне User, а не CandidateProfile (§5.1 кладёт его в
профиль): по fsp_id юзер находится/создаётся при входе через FSP ID до
выбора роли — а работодателю профиля кандидата вообще нет. Профильные
схемы отдают fsp_id джойном (см. candidates/schemas.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base


class User(Base):
    # "user" — зарезервированное слово PG; SQLAlchemy кавычит его в DDL
    # автоматически (dialect reserved words)
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # NULL, пока юзер создан без почты (вход через FSP ID)
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True, index=True, nullable=True
    )
    # sub из userinfo мок-OIDC fsp_registry = fsp_id; NULL без FSP-входа
    fsp_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    # candidate|employer; NULL до онбординга (роль выбирается один раз,
    # POST /users/me/role)
    role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)
    # согласия 152-ФЗ при регистрации (§7.1): обработка ПДн — обязательно,
    # публикация профиля работодателям — отдельный чекбокс
    consent_pd: Mapped[bool] = mapped_column(default=False)
    consent_publish: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
