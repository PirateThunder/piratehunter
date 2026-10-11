"""vacancy + application (§7.7): вакансии с обязательной вилкой,
отклики кандидатов

Revision ID: 20261011_vacancies
Revises: 20261008_init
Create Date: 2026-10-11

vacancy: вилка обязательна + salary_type gross|net (инвариант ТЗ §2.2),
статусы draft|published|closed, external_id уникален в рамках компании
(ATS-идемпотентность, §17).
application: отклик кандидата, UNIQUE (vacancy_id, candidate_id),
статусы sent|viewed|invited|rejected.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models import JSONBVariant

revision: str = "20261011_vacancies"
down_revision: str | Sequence[str] | None = "20261008_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("spec_slug", sa.String(64), nullable=False),
        sa.Column("grade", sa.String(16), nullable=False),
        sa.Column("stack_must", JSONBVariant, nullable=False),
        sa.Column("stack_nice", JSONBVariant, nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("salary_type", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"], ["company.user_id"], ondelete="CASCADE",
            name="vacancy_company_id_fkey",
        ),
        sa.CheckConstraint(
            "salary_from > 0", name="salary_from_positive"
        ),
        sa.CheckConstraint(
            "salary_from <= salary_to", name="salary_range"
        ),
        sa.CheckConstraint(
            "salary_type IN ('gross', 'net')", name="salary_type"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'closed')", name="status"
        ),
        sa.UniqueConstraint("company_id", "external_id"),
    )
    op.create_index("ix_vacancy_company_id", "vacancy", ["company_id"])

    op.create_table(
        "application",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vacancy_id", sa.String(36), nullable=False),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.id"], ondelete="CASCADE",
            name="application_vacancy_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["user.id"], ondelete="CASCADE",
            name="application_candidate_id_fkey",
        ),
        sa.UniqueConstraint("vacancy_id", "candidate_id"),
        sa.CheckConstraint(
            "status IN ('sent', 'viewed', 'invited', 'rejected')",
            name="status",
        ),
    )
    op.create_index("ix_application_vacancy_id", "application",
                    ["vacancy_id"])
    op.create_index("ix_application_candidate_id", "application",
                    ["candidate_id"])


def downgrade() -> None:
    op.drop_table("application")
    op.drop_table("vacancy")
