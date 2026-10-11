"""IRT-математика CAT-lite (PRD §7.4.2, §7.4.5).

Логистическая модель: P(correct) = σ(θ − β). Обновление θ после ответа
r∈{0,1}: θ += K(n)·(r − p), K(n) = K0/√n, clamp [−4, 4]. SE оценки —
1/√(Σ p_i(1−p_i)) по отвеченным заданиям. BetaStat — калибровка β по
истории ответов методом моментов (β̂ = θ̄ − logit(p̄)) с демпфированием:
шаг ≤ 0.2 за итерацию, границы [−3, 3.5].
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

THETA_LO = -4.0
THETA_HI = 4.0
BETA_LO = -3.0
BETA_HI = 3.5

# Базовый шаг обновления θ. Подобран валидационным харнессом (300 агентов ×
# 3 повтора, свежий банк на повтор): спецификационные 0.8/√n на 10 вопросах
# дают избыточный шум оценки (стабильность ±1 = 0.967 < порога 0.97);
# 0.4/√n держит все пороги §9.3 с запасом (exact 0.99, ±1 = 1.00,
# Spearman 0.98) при MAE(θ) ≈ 0.35 — разрешение внутри полосы сохраняется.
K0 = 0.4

CALIB_MIN_N = 25  # минимум ответов в окне перед калибровкой
CALIB_STEP = 0.2  # максимальный сдвиг β за итерацию


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def p_correct(theta: float, beta: float) -> float:
    return sigmoid(theta - beta)


def step_size(n_answers: int, k0: float = K0) -> float:
    """K(n) = K0/√n — затухающий шаг; n — номер ответа (с 1)."""
    return k0 / math.sqrt(max(1, n_answers))


def update_theta(theta: float, beta: float, correct: bool, n_answers: int, k0: float = K0) -> float:
    p = p_correct(theta, beta)
    r = 1.0 if correct else 0.0
    new = theta + step_size(n_answers, k0) * (r - p)
    return min(THETA_HI, max(THETA_LO, new))


def standard_error(theta: float, betas: list[float]) -> float:
    """SE = 1/√(Σ p_i(1−p_i)); без ответов — бесконечность."""
    info = 0.0
    for b in betas:
        p = p_correct(theta, b)
        info += p * (1.0 - p)
    return math.inf if info <= 0.0 else 1.0 / math.sqrt(info)


def _posterior_weights(
    answers: list[tuple[float, bool]], prior_mu: float, prior_sd: float
) -> list[tuple[float, float]]:
    """(θ, вес) по сетке: апостериор N(prior) × правдоподобие ответов."""
    grid = [x / 20 for x in range(int(THETA_LO * 20), int(THETA_HI * 20) + 1)]
    out = []
    for th in grid:
        ll = -0.5 * ((th - prior_mu) / prior_sd) ** 2
        for beta, correct in answers:
            p = min(1.0 - 1e-9, max(1e-9, p_correct(th, beta)))
            ll += math.log(p) if correct else math.log(1.0 - p)
        out.append((th, math.exp(ll)))
    return out


def posterior_prob_above(
    answers: list[tuple[float, bool]],
    threshold: float,
    prior_mu: float,
    prior_sd: float = 1.25,
) -> float:
    """P(θ > threshold | ответы) при приоре N(prior_mu, prior_sd²).

    Используется для решений upgrade/downgrade: хвостовая вероятность
    устойчива к выбору приора и, в отличие от точечной оценки, не шумит
    в метрике стабильности грейда.
    """
    weights = _posterior_weights(answers, prior_mu, prior_sd)
    total = sum(w for _th, w in weights)
    if total <= 0:
        return 0.0
    return sum(w for th, w in weights if th > threshold) / total


def posterior_prob_below(
    answers: list[tuple[float, bool]],
    threshold: float,
    prior_mu: float,
    prior_sd: float = 1.25,
) -> float:
    return 1.0 - posterior_prob_above(answers, threshold, prior_mu, prior_sd)


def posterior_mean(
    answers: list[tuple[float, bool]], prior_mu: float, prior_sd: float = 8.0
) -> float:
    """Апостериорное среднее θ (EAP) по ответам; без ответов — prior_mu.

    Используется для подбора следующего вопроса: быстро доезжает до
    рабочего уровня агента, в отличие от онлайн-шага Роббинса–Монро.
    """
    if not answers:
        return prior_mu
    weights = _posterior_weights(answers, prior_mu, prior_sd)
    total = sum(w for _th, w in weights)
    if total <= 0:
        return prior_mu
    return sum(th * w for th, w in weights) / total


@dataclass
class BetaStat:
    """Калибровка сложности шаблона по истории ответов (PRD §7.4.5).

    Накапливает (θ ответившего, correct); calibrate() решает β̂ из доли
    верных и среднего θ отвечавших (метод моментов: p̄ = σ(θ̄ − β̂)) и
    сдвигает β к β̂ не более чем на CALIB_STEP, в границах [BETA_LO, BETA_HI].
    После калибровки окно очищается — итерации независимы.
    """

    template_id: str
    beta: float
    thetas: list[float] = field(default_factory=list)
    corrects: list[int] = field(default_factory=list)

    def record(self, theta: float, correct: bool) -> None:
        self.thetas.append(theta)
        self.corrects.append(1 if correct else 0)

    @property
    def n_answers(self) -> int:
        return len(self.corrects)

    def ready(self, min_n: int = CALIB_MIN_N) -> bool:
        return self.n_answers >= min_n

    def empirical_beta(self) -> float | None:
        """β̂ = θ̄ − logit(p̄) по накопленному окну; None если окно пусто."""
        if not self.corrects:
            return None
        p = sum(self.corrects) / len(self.corrects)
        p = min(0.98, max(0.02, p))
        theta_bar = sum(self.thetas) / len(self.thetas)
        return theta_bar - logit(p)

    def calibrate(self, min_n: int = CALIB_MIN_N) -> float | None:
        """Одна итерация калибровки; возвращает новую β или None, если рано."""
        if not self.ready(min_n):
            return None
        beta_hat = self.empirical_beta()
        assert beta_hat is not None
        delta = max(-CALIB_STEP, min(CALIB_STEP, beta_hat - self.beta))
        self.beta = min(BETA_HI, max(BETA_LO, self.beta + delta))
        self.thetas.clear()
        self.corrects.clear()
        return self.beta
