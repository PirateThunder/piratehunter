"""Стартовый банк заданий из фабрик (PRD §7.4.1, §10).

Строится один раз в lifespan (sync-работа — через run_in_threadpool) и
держится в app.state; в БД (item_template) пишется версионный слой §5.2.
Полный 20-seed sanity — задача CLI bank-build; здесь только дымовая
проверка одним seed: шаблон, не генерирующий экземпляр, гасится сразу.
"""

from __future__ import annotations

import random

from app.config import Settings
from engine.catalog import MCQ_TOPICS, SQL_TOPICS, get_specialization
from itembank import BankRegistry, factory_mcq, factory_sql


def build_startup_bank(settings: Settings) -> BankRegistry:
    reg = BankRegistry()
    for spec in settings.bank_spec_list:
        get_specialization(spec)  # валидация slug'ов конфига на старте
        rng = random.Random(f"core-api-bank:{spec}:{settings.bank_seed}")
        mcq_topics = MCQ_TOPICS.get(spec, ())
        sql_topics = SQL_TOPICS.get(spec, ())
        if mcq_topics:
            for i, topic in enumerate(mcq_topics):
                cnt = settings.bank_mcq_per_spec // len(mcq_topics) + (
                    1 if i < settings.bank_mcq_per_spec % len(mcq_topics) else 0
                )
                for t in factory_mcq.make_templates(spec, topic, cnt, rng):
                    reg.add(t)
        if sql_topics:
            for i, topic in enumerate(sql_topics):
                cnt = settings.bank_sql_per_spec // len(sql_topics) + (
                    1 if i < settings.bank_sql_per_spec % len(sql_topics) else 0
                )
                for t in factory_sql.make_templates(spec, topic, cnt, rng):
                    reg.add(t)
    # дымовая проверка: шаблон обязан сгенерировать валидный экземпляр
    for t in reg.filter(active_only=False):
        try:
            inst = t.make(0)
            if not inst.check(inst.reference):
                t.active = False
        except Exception:
            t.active = False
    return reg
