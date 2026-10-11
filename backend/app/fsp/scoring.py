"""fsp_score по правилам Q&A 06.10 (PRD §7.9).

Дисциплины и уровни соревнований НЕ ранжируем («все соревнования равно
важны»). Считаем результативность и число:

    победитель (place == 1)        1.0
    призёр (диплом I–III)          0.7
    призовое место (place 2–3)     0.5
    участие                        0.15 × 0.5^(i-1)  (i — номер явки)
    мероприятие                    0.05 × 0.5^(i-1)

Затухание за повторные явки — защита от набивания профиля одними
онлайн-явками. Командный результат учитываем как обычное достижение
(вклад честно не выделить). Давность не штрафуем (архива нет).
Итог — сумма, cap 1.0.
"""

WEIGHT_WINNER = 1.0
WEIGHT_DIPLOMA = 0.7
WEIGHT_PRIZE_PLACE = 0.5
WEIGHT_PARTICIPATION = 0.15
WEIGHT_EVENT = 0.05
DECAY = 0.5
CAP = 1.0


def _contest_weight(contest: dict) -> float | None:
    """Вес достижения; None — «просто участие» (считается с затуханием
    снаружи). Командное место считаем как личное (Q&A)."""
    place = contest.get("place")
    if place is None:
        team_result = contest.get("team_result") or {}
        place = team_result.get("place")
    if place == 1:
        return WEIGHT_WINNER
    if contest.get("diploma") in (1, 2, 3):
        return WEIGHT_DIPLOMA
    if place is not None and place <= 3:
        return WEIGHT_PRIZE_PLACE
    return None


def compute_fsp_score(profile: dict | None) -> float:
    """0..1; None (нет истории ФСП, 404 реестра) → 0 без штрафа сверх
    веса фактора в скоринге core."""
    if not profile:
        return 0.0
    total = 0.0
    participation_idx = 0
    for contest in profile.get("contests") or []:
        weight = _contest_weight(contest)
        if weight is None:
            total += WEIGHT_PARTICIPATION * DECAY**participation_idx
            participation_idx += 1
        else:
            total += weight
    for event_idx, _event in enumerate(profile.get("events") or []):
        total += WEIGHT_EVENT * DECAY**event_idx
    return round(min(total, CAP), 4)
