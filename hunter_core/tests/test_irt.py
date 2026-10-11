"""IRT-математика: сигмоида, обновление θ, SE, калибровка BetaStat."""

import math
import random

from engine import irt


def test_sigmoid_properties():
    assert irt.sigmoid(0.0) == 0.5
    assert irt.sigmoid(10) > 0.9999
    assert irt.sigmoid(-10) < 0.0001
    assert abs(irt.sigmoid(2.0) + irt.sigmoid(-2.0) - 1.0) < 1e-12


def test_p_correct_monotone():
    assert irt.p_correct(1.0, 0.0) > irt.p_correct(0.0, 0.0) > irt.p_correct(-1.0, 0.0)
    assert irt.p_correct(0.0, 0.0) == 0.5


def test_update_theta_direction_and_clamp():
    up = irt.update_theta(0.0, 0.0, True, 1)
    down = irt.update_theta(0.0, 0.0, False, 1)
    assert up > 0.0 > down
    # clamp в [−4, 4]
    assert irt.update_theta(3.99, -3.0, True, 1) <= irt.THETA_HI
    assert irt.update_theta(-3.99, 3.0, False, 1) >= irt.THETA_LO


def test_step_size_decays():
    assert irt.step_size(1) > irt.step_size(4) > irt.step_size(9)
    assert irt.step_size(1) == irt.K0


def test_standard_error():
    assert irt.standard_error(0.0, []) == math.inf
    se1 = irt.standard_error(0.0, [0.0])
    se5 = irt.standard_error(0.0, [0.0] * 5)
    assert se5 < se1
    assert abs(se1 - 2.0) < 1e-9  # 1/sqrt(0.25)


def test_beta_stat_calibration_converges():
    # ответы агентов на задание с истинной β=0.8; стартуем с ошибочной β=1.6
    rng = random.Random(5)
    stat = irt.BetaStat(template_id="t", beta=1.6)
    beta_true = 0.8
    for _ in range(150):
        theta = rng.gauss(1.0, 0.3)
        correct = rng.random() < irt.p_correct(theta, beta_true)
        stat.record(theta, correct)
        if stat.n_answers >= 30:
            stat.calibrate(min_n=30)
    empirical = stat.empirical_beta() or beta_true
    assert abs(stat.beta - beta_true) < 0.5  # движение в сторону истины
    assert stat.beta < 1.6
    assert irt.BETA_LO <= stat.beta <= irt.BETA_HI
    assert empirical is not None


def test_beta_stat_respects_window():
    stat = irt.BetaStat(template_id="t", beta=0.0)
    assert stat.calibrate() is None  # окно пустое
    for _ in range(10):
        stat.record(0.0, True)
    assert stat.calibrate() is None  # < CALIB_MIN_N
