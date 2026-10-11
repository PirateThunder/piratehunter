"""Константы кандидатского домена."""

# статусы GradeState (PRD §5.1, §7.4.3)
GRADE_UNVERIFIED = "unverified"
GRADE_CONFIRMED = "confirmed"
GRADE_UPGRADE_OFFER = "upgrade_offer"
GRADE_DOWNGRADE_OFFER = "downgrade_offer"
GRADE_STATUSES = (
    GRADE_UNVERIFIED,
    GRADE_CONFIRMED,
    GRADE_UPGRADE_OFFER,
    GRADE_DOWNGRADE_OFFER,
)

# дефолтные настройки приватности (§7.2): анонимность — опция, не дефолт
DEFAULT_PRIVACY = {"anonymous": False, "show_fsp": True, "show_stack": True}
