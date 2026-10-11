"""Каталог §6: границы θ-полос, сериализация."""

from engine.catalog import (
    GRADES,
    SPECIALIZATIONS,
    catalog_dict,
    get_grade,
    grade_for_theta,
    next_grade,
    prev_grade,
)


def test_seven_specializations_with_topics():
    assert len(SPECIALIZATIONS) == 7
    slugs = {s.slug for s in SPECIALIZATIONS}
    assert slugs == {"backend", "frontend", "fullstack", "mobile", "qa", "devops", "data-ml"}
    for s in SPECIALIZATIONS:
        assert 5 <= len(s.topics) <= 8, s.slug


def test_grade_bands_boundaries():
    # intern < −1 ≤ junior < 0.5 ≤ middle < 2 ≤ senior
    assert grade_for_theta(-4.0).slug == "intern"
    assert grade_for_theta(-1.0001).slug == "intern"
    assert grade_for_theta(-1.0).slug == "junior"
    assert grade_for_theta(0.4999).slug == "junior"
    assert grade_for_theta(0.5).slug == "middle"
    assert grade_for_theta(1.9999).slug == "middle"
    assert grade_for_theta(2.0).slug == "senior"
    assert grade_for_theta(4.0).slug == "senior"


def test_grade_medians_and_navigation():
    assert get_grade("intern").median == -2.5
    assert get_grade("junior").median == -0.25
    assert get_grade("middle").median == 1.25
    assert get_grade("senior").median == 3.0
    assert next_grade("middle").slug == "senior"
    assert next_grade("senior") is None
    assert prev_grade("junior").slug == "intern"
    assert prev_grade("intern") is None


def test_catalog_serializable():
    import json

    json.dumps(catalog_dict(), ensure_ascii=False)
    assert len(catalog_dict()["grades"]) == 4


def test_grade_descriptions_are_skill_based():
    """Грейд — уровень навыка по тесту (PRD §6), без упоминания стажа/годов."""
    for g in GRADES:
        text = f"{g.title} {g.description}".lower()
        assert "опыт" not in text
        assert "стаж" not in text
        assert "лет" not in text and "год" not in text
