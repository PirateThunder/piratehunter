"""init: user, candidate_profile, grade_state, company, need, invitation

Revision ID: 20261008_init
Revises: None
Create Date: 2026-10-08

Начальная схема ph_back по PRD §5.1 (фаза 1): пользователи и auth-
идентичности, профиль кандидата (контакты отдельными полями — правила
видимости §7.6), статус грейда, компания, потребность, приглашение с
обязательной вилкой ЗП (gross|net, инвариант ТЗ §2.2 — CHECK'ами).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models import JSONBVariant, StringArray

revision: str = "20261008_init"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("fsp_id", sa.String(64), nullable=True),
        sa.Column("role", sa.String(16), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=False),
        sa.Column("consent_pd", sa.Boolean(), nullable=False),
        sa.Column("consent_publish", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_fsp_id", "user", ["fsp_id"], unique=True)

    op.create_table(
        "candidate_profile",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("fio", sa.String(300), nullable=False),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("contacts", JSONBVariant, nullable=False),
        sa.Column("stack", StringArray, nullable=False),
        sa.Column("spec_slug", sa.String(64), nullable=True),
        sa.Column("grade_claimed", sa.String(16), nullable=True),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("roles", StringArray, nullable=False),
        sa.Column("soft_skills", StringArray, nullable=False),
        sa.Column("about", sa.String(), nullable=True),
        sa.Column("resume_text", sa.String(), nullable=True),
        sa.Column("privacy", JSONBVariant, nullable=False),
        sa.Column("fsp_score", sa.Float(), nullable=False),
        sa.Column("fsp_data", JSONBVariant, nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE",
            name="candidate_profile_user_id_fkey",
        ),
    )

    op.create_table(
        "grade_state",
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column("grade_verified", sa.String(16), nullable=True),
        sa.Column("theta", sa.Float(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("grade_changed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["user.id"], ondelete="CASCADE",
            name="grade_state_candidate_id_fkey",
        ),
    )

    op.create_table(
        "company",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column("contacts", JSONBVariant, nullable=False),
        sa.Column("site", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE",
            name="company_user_id_fkey",
        ),
    )

    op.create_table(
        "need",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=False),
        sa.Column("parsed", JSONBVariant, nullable=True),
        sa.Column("stack_must", StringArray, nullable=False),
        sa.Column("stack_nice", StringArray, nullable=False),
        sa.Column("spec_slug", sa.String(64), nullable=True),
        sa.Column("grade", sa.String(16), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["company.user_id"], ondelete="CASCADE",
            name="need_company_id_fkey",
        ),
        sa.CheckConstraint(
            "salary_from IS NULL OR salary_to IS NULL "
            "OR salary_from <= salary_to",
            name="salary_range",
        ),
    )
    op.create_index("ix_need_company_id", "need", ["company_id"])

    op.create_table(
        "invitation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("salary_type", sa.String(8), nullable=False),
        sa.Column("contact_method", sa.String(300), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "status_at", sa.DateTime(), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["company.user_id"], ondelete="CASCADE",
            name="invitation_company_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["user.id"], ondelete="CASCADE",
            name="invitation_candidate_id_fkey",
        ),
        sa.CheckConstraint(
            "salary_from > 0", name="salary_from_positive"
        ),
        sa.CheckConstraint(
            "salary_from <= salary_to", name="salary_range"
        ),
        sa.CheckConstraint(
            "salary_type IN ('gross', 'net')",
            name="salary_type",
        ),
        sa.CheckConstraint(
            "status IN ('sent', 'viewed', 'accepted', 'declined')",
            name="status",
        ),
    )
    op.create_index("ix_invitation_company_id", "invitation", ["company_id"])
    op.create_index(
        "ix_invitation_candidate_id", "invitation", ["candidate_id"]
    )


def downgrade() -> None:
    op.drop_table("invitation")
    op.drop_table("need")
    op.drop_table("company")
    op.drop_table("grade_state")
    op.drop_table("candidate_profile")
    op.drop_table("user")
