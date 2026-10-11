"""Адаптивный тест-движок CAT-lite (PRD §7.4.2, §7.4.3).

Старт: θ₀ = медиана полосы заявляемого грейда. Следующий вопрос — из
неиспользованных шаблонов специализации: темы round-robin, внутри темы
argmin|β−θ| (максимум информации); экземпляр — со свежим seed. После
каждого ответа — обновление θ (θ += K(n)·(r−p), K(n)=K0/√n) и SE
(engine/irt.py). Стоп: full = 10 вопросов / express = 4, или SE < 0.35
(ранняя уверенность).

Оценка и решения — раздельно (конструктив CAT-lite):
- θ (онлайн, стохастическая аппроксимация θ += K(n)·(r−p)) — отчётная
  точечная оценка: стабильна между повторами (метрика §9.2.1), но за 10
  вопросов не успевает дойти до θ_true при сильном расхождении с
  заявленным грейдом;
- подбор следующего вопроса ведётся по апостериорному среднему (EAP со
  слабоинформативным приором): оно быстро доезжает до рабочего уровня,
  поэтому ответы информативны даже при «промахнувшемся» заявлении;
- исход (outcome) — по апостериорной вероятности хвоста: upgrade_offer
  при P(θ > низ следующего грейда) ≥ offer_confidence, downgrade_offer
  при P(θ < низ заявленного) ≥ offer_confidence, иначе confirmed.
  Хвостовая вероятность чувствительна к «сильному прохождению» (механика
  PRD §7.4.3) и не шумит в точечной стабильности грейда. Без
  принудительного понижения: при downgrade_offer grade_verified = null;
  при upgrade_offer заявленный грейд подтверждается и предлагается тест
  на повышение.

API — чистый Python, без HTTP.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any

from engine import irt
from engine.catalog import get_grade, get_specialization, grade_for_theta, next_grade
from itembank.model import Instance, ItemTemplate
from itembank.registry import BankRegistry

MODES = ("full", "express")


@dataclass
class CatConfig:
    full_questions: int = 10
    express_questions: int = 4
    se_stop: float = 0.35
    # порог апостериорной уверенности для upgrade/downgrade предложений
    offer_confidence: float = 0.7
    # масштаб приора N(медиана полосы заявленного грейда, prior_sd²);
    # 8.0 — слабоинформативный (ширина шкалы): решение ведут ответы
    prior_sd: float = 8.0
    # default_factory: читаем irt.K0 в момент создания конфига, а не при
    # импорте модуля — иначе подбор K0 валидацией не влиял бы на движок.
    k0: float = field(default_factory=lambda: irt.K0)


@dataclass
class AskedItem:
    template_id: str
    seed: int
    topic: str
    kind: str
    beta: float
    correct: bool
    theta_after: float


class TestEngine:
    """Сессионный движок теста; банк инжектируется, HTTP-слоя нет."""

    def __init__(
        self,
        bank: BankRegistry,
        config: CatConfig | None = None,
        seed: int | str | None = None,
    ) -> None:
        self.bank = bank
        self.config = config or CatConfig()
        self._rng = random.Random(seed)
        self.spec = ""
        self.grade_claimed = ""
        self.mode = "full"
        self.theta = 0.0  # онлайн-оценка (стохастическая аппроксимация)
        self._theta_sel = 0.0  # оценка для подбора вопросов (EAP)
        self.se = math.inf
        self.asked: list[AskedItem] = []
        self.status = "new"
        self._used: set[str] = set()
        self._pending: tuple[ItemTemplate, Instance] | None = None

    @classmethod
    def restore(
        cls,
        bank: BankRegistry,
        *,
        spec: str,
        grade_claimed: str,
        mode: str,
        theta: float,
        asked: list[AskedItem],
        pending: tuple[ItemTemplate, Instance] | None = None,
        config: CatConfig | None = None,
        seed: int | str | None = None,
    ) -> TestEngine:
        """Восстанавливает состояние сессии из хранилища (core-api: state в PG).

        asked — уже заданные вопросы; pending — открытый вопрос (шаблон +
        переинстанцированный по seed экземпляр). SE и оценка для подбора
        (_theta_sel) пересчитываются из истории ответов.
        """
        engine = cls(bank, config=config, seed=seed)
        engine.spec = spec
        engine.grade_claimed = grade_claimed
        engine.mode = mode
        engine.theta = theta
        engine.asked = list(asked)
        engine.se = irt.standard_error(theta, [a.beta for a in asked])
        engine._used = {a.template_id for a in asked}
        engine._theta_sel = irt.posterior_mean(
            [(a.beta, a.correct) for a in asked],
            get_grade(grade_claimed).median,
            engine.config.prior_sd,
        )
        engine.status = "active"
        engine._pending = pending
        return engine

    @property
    def max_questions(self) -> int:
        return self.config.full_questions if self.mode == "full" else self.config.express_questions

    @property
    def current(self) -> Instance | None:
        return self._pending[1] if self._pending else None

    def start(self, spec: str, grade_claimed: str, mode: str = "full") -> Instance:
        get_specialization(spec)  # валидация slug'ов по каталогу
        grade = get_grade(grade_claimed)
        if mode not in MODES:
            raise ValueError(f"неизвестный режим {mode!r}; доступны: {', '.join(MODES)}")
        if not self.bank.filter(spec=spec):
            raise ValueError(f"в банке нет активных шаблонов специализации {spec!r}")
        self.spec = spec
        self.grade_claimed = grade_claimed
        self.mode = mode
        self.theta = grade.median
        self._theta_sel = grade.median
        self.se = math.inf
        self.asked = []
        self._used = set()
        self.status = "active"
        inst = self._draw()
        assert inst is not None  # банк непуст — проверено выше
        return inst

    def next_question(self) -> Instance | None:
        if self.status != "active" or self._pending is not None:
            return self.current
        return self._draw()

    def submit(self, answer: Any) -> dict[str, Any]:
        """Принимает ответ; возвращает следующий вопрос или финальный результат."""
        if self.status != "active":
            raise RuntimeError("сессия не активна")
        if self._pending is None:
            raise RuntimeError("нет открытого вопроса — сначала next_question()")
        template, inst = self._pending
        correct = inst.check(answer)
        n = len(self.asked) + 1
        self.theta = irt.update_theta(self.theta, inst.beta, correct, n, self.config.k0)
        self.asked.append(
            AskedItem(
                template_id=template.id,
                seed=inst.seed,
                topic=template.topic,
                kind=template.kind,
                beta=inst.beta,
                correct=correct,
                theta_after=self.theta,
            )
        )
        self.se = irt.standard_error(self.theta, [a.beta for a in self.asked])
        self._theta_sel = irt.posterior_mean(
            [(a.beta, a.correct) for a in self.asked],
            get_grade(self.grade_claimed).median,
            self.config.prior_sd,
        )
        self._pending = None
        stop = len(self.asked) >= self.max_questions or self.se < self.config.se_stop
        nxt = None if stop else self._draw()
        if stop or nxt is None:
            self.status = "finished"
            return {"finished": True, "correct": correct, "result": self._result()}
        return {
            "finished": False,
            "correct": correct,
            "theta": self.theta,
            "se": self.se,
            "next": nxt,
        }

    def _pick(self) -> ItemTemplate | None:
        avail = self.bank.filter(spec=self.spec, exclude=self._used)
        if not avail:
            return None
        counts: dict[str, int] = {}
        for a in self.asked:
            counts[a.topic] = counts.get(a.topic, 0) + 1
        topic = min({t.topic for t in avail}, key=lambda tp: (counts.get(tp, 0), tp))
        candidates = [t for t in avail if t.topic == topic]
        return min(candidates, key=lambda t: (abs(t.beta - self._theta_sel), t.id))

    def _draw(self) -> Instance | None:
        template = self._pick()
        if template is None:
            return None
        seed = self._rng.randrange(2**31)
        inst = template.make(seed)
        self._used.add(template.id)
        self._pending = (template, inst)
        return inst

    def _result(self) -> dict[str, Any]:
        band = get_grade(self.grade_claimed)
        following = next_grade(band.slug)
        answers = [(a.beta, a.correct) for a in self.asked]
        p_down = irt.posterior_prob_below(answers, band.lo, band.median, self.config.prior_sd)
        p_up = (
            irt.posterior_prob_above(answers, following.lo, band.median, self.config.prior_sd)
            if following is not None
            else 0.0
        )
        if p_down >= self.config.offer_confidence:
            outcome, verified = "downgrade_offer", None
        elif p_up >= self.config.offer_confidence:
            # заявленный грейд подтверждён + предложение пройти тест на повышение
            outcome, verified = "upgrade_offer", band.slug
        else:
            outcome, verified = "confirmed", band.slug
        breakdown: dict[str, dict[str, int]] = {}
        for a in self.asked:
            b = breakdown.setdefault(a.topic, {"asked": 0, "correct": 0})
            b["asked"] += 1
            b["correct"] += int(a.correct)
        return {
            "theta": round(self.theta, 3),
            "se": round(self.se, 3),
            "outcome": outcome,
            "grade_verified": verified,
            "grade_assigned": grade_for_theta(self.theta).slug,
            "grade_claimed": self.grade_claimed,
            "spec": self.spec,
            "mode": self.mode,
            "p_upgrade": round(p_up, 3),
            "p_downgrade": round(p_down, 3),
            "asked": [asdict(a) for a in self.asked],
            "breakdown": breakdown,
        }
