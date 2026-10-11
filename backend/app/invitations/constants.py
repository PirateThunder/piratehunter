"""Статусы приглашения (PRD §5.1, §7.6): sent → viewed → accepted |
declined. viewed ставится при первом открытии кандидатом."""

SENT = "sent"
VIEWED = "viewed"
ACCEPTED = "accepted"
DECLINED = "declined"

STATUSES = (SENT, VIEWED, ACCEPTED, DECLINED)

# из каких статусов можно принять/отклонить
OPEN_STATUSES = (SENT, VIEWED)
