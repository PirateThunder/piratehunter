"""Фабрики: sanity-конвергенция чекера на эталоне, уникальность экземпляров,
сериализация банка (roundtrip восстанавливает генераторы)."""

import random

import pytest

from itembank import factory_mcq, factory_sql
from itembank.registry import BankRegistry, sanity_check_template
from validation.harness import build_bank


@pytest.fixture(scope="module")
def bank() -> BankRegistry:
    return build_bank("backend", seed=101, mcq_n=9, sql_n=6)


def test_factories_produce_templates(bank):
    templates = bank.filter()
    assert len(templates) >= 12
    kinds = {t.kind for t in templates}
    assert kinds == {"mcq", "sql"}
    for t in templates:
        assert -3.0 <= t.beta <= 3.5
        assert t.grade_band in {"intern", "junior", "middle", "senior"}


def test_sanity_checker_converges(bank):
    """20 seeds × каждый шаблон: чекер обязан сходиться на эталоне."""
    reports = [sanity_check_template(t, n_seeds=20) for t in bank.filter()]
    failed = [r for r in reports if not r.ok]
    assert not failed, f"отбракованы: {[r.template_id for r in failed]}"


def test_instances_unique_per_seed(bank):
    for t in bank.filter():
        a, b = t.make(1), t.make(2)
        key_a = a.question_text if a.kind == "mcq" else a.payload["setup_sql"]
        key_b = b.question_text if b.kind == "mcq" else b.payload["setup_sql"]
        assert key_a != key_b, f"{t.id}: экземпляры двух seed'ов совпали"


def test_mcq_options_and_distractors():
    rng = random.Random(3)
    templates = factory_mcq.make_templates("backend", "python", 8, rng)
    assert templates
    for t in templates:
        inst = t.make(7)
        options = inst.payload["options"]
        assert len(set(options)) == 4
        assert inst.check(inst.reference)
        for opt in options:
            if opt != inst.reference:
                assert not inst.check(opt)


def test_sql_checker_strictness():
    rng = random.Random(9)
    templates = factory_sql.make_templates("backend", "sql", 4, rng)
    assert templates
    for t in templates:
        inst = t.make(11)
        assert inst.check(inst.reference)
        assert not inst.check("SELECT 1 WHERE 0")
        assert not inst.check("SELECT nonsense FROM nowhere")
        assert not inst.check(12345)


def test_bank_json_roundtrip(bank, tmp_path):
    path = tmp_path / "bank.json"
    bank.to_json(path)
    loaded = BankRegistry.from_json(path)
    assert len(loaded) == len(bank)
    for t in bank.filter():
        t2 = loaded.get(t.id)
        assert t2.to_record() == t.to_record()
        # генератор восстановлен: тот же seed → тот же эталон
        assert t2.make(5).reference == t.make(5).reference


def test_registry_filters_and_exclude(bank):
    python_templates = bank.filter(spec="backend", topic="python")
    assert python_templates
    excluded = bank.filter(spec="backend", exclude=[python_templates[0].id])
    assert len(excluded) == len(bank.filter(spec="backend")) - 1
    bank.deactivate(python_templates[0].id)
    assert len(bank.filter(spec="backend")) == len(
        bank.filter(spec="backend", active_only=False)
    ) - 1
    bank.get(python_templates[0].id).active = True
