"""Статусы вакансий и откликов (PRD §5.1, §7.7)."""

# vacancy.status
VACANCY_DRAFT = "draft"
VACANCY_PUBLISHED = "published"
VACANCY_CLOSED = "closed"
VACANCY_STATUSES = (VACANCY_DRAFT, VACANCY_PUBLISHED, VACANCY_CLOSED)

# application.status: sent → viewed (авто при первом GET списка у
# работодателя) → invited | rejected
APP_SENT = "sent"
APP_VIEWED = "viewed"
APP_INVITED = "invited"
APP_REJECTED = "rejected"
APP_STATUSES = (APP_SENT, APP_VIEWED, APP_INVITED, APP_REJECTED)

# переходы PATCH работодателя
APP_PATCHABLE = (APP_VIEWED, APP_INVITED, APP_REJECTED)
