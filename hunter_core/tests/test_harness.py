"""Валидационный харнесс на малом N: прогон отрабатывает, файлы пишутся."""

import json

from validation.harness import pearson, run_validation, session_overlap, spearman


def test_spearman_and_pearson():
    assert abs(spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    # связи — midranks, не падает
    assert 0.9 < spearman([1, 1, 2, 3], [1, 1, 2, 3]) <= 1.0


def test_session_overlap():
    import pytest

    assert session_overlap([{"a", "b"}, {"b", "c"}])["mean_jaccard"] == pytest.approx(
        1 / 3, abs=1e-4
    )
    assert session_overlap([{"a"}, {"a"}])["mean_jaccard"] == 1.0
    assert session_overlap([])["mean_jaccard"] == 0.0


def test_harness_small_run_writes_files(tmp_path):
    report = run_validation(
        n_agents=20, repeats=2, out_dir=tmp_path, seed=5, quick=True, verbose=False
    )
    m = report["metrics"]
    for key in ("stability_exact", "stability_pm1", "spearman", "adjacent_confusion",
                "confusion_matrix", "instance_equivalence", "beta_calibration",
                "session_overlap"):
        assert key in m
    assert isinstance(report["overall_pass"], bool)
    assert len(m["confusion_matrix"]) == 4
    # на малом прогоне ключевые пороги тоже обязаны держаться
    assert m["stability_pm1"] >= 0.97
    assert m["spearman"] >= 0.85
    for name in ("validation.json", "summary.txt", "theta_scatter.png", "confusion.png"):
        path = tmp_path / name
        assert path.exists() and path.stat().st_size > 0, name
    loaded = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
    assert loaded["params"]["n_agents"] == 20
    assert "ИТОГ" in (tmp_path / "summary.txt").read_text(encoding="utf-8")


def test_matching_eval_passes_threshold(tmp_path):
    from validation.matching_eval import run_matching_eval

    report = run_matching_eval(out_path=tmp_path / "matching.json")
    assert report["metrics"]["precision_at_5"] >= 0.8
    assert report["overall_pass"]
    assert report["metrics"]["needs_evaluated"] == 20
    assert (tmp_path / "matching.json").exists()
    # отчёт объяснимости: у топ-1 каждой потребности есть разложение по факторам
    with_explanation = [n for n in report["per_need"] if n["top1_explanation"]]
    assert with_explanation
    assert len(with_explanation[0]["top1_explanation"]) == 4
