"""Фабрика sql-шаблонов (PRD §7.4.1, фабрики).

Домены: employees/departments, orders/customers, students/enrollments.
Схема и наполнение параметризуются seed'ом (sqlite in-memory), эталонный
запрос — из библиотеки паттернов: JOIN+GROUP BY+HAVING, подзапрос с
агрегатом, GROUP BY HAVING против глобального агрегата, оконная функция
(ROW_NUMBER, уровень middle/senior). check(answer_sql) выполняет ответ и
сравнивает мультимножества строк с эталоном (числа с допуском 1e-6), лимит
на исполнение — через progress-handler sqlite.

Слоты, влияющие на сложность (пороги, направление сравнения), фиксируются
в opts шаблона; seed варьирует только данные → β постоянна внутри шаблона.
"""

from __future__ import annotations

import random
import sqlite3
import zlib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from engine.catalog import grade_for_theta
from itembank.model import TIME_LIMITS, Instance, ItemGenerationError, ItemTemplate
from itembank.registry import register_factory

FACTORY_ID = "sql"

_MAX_ATTEMPTS = 15  # перегенераций данных внутри instantiate
ROW_LIMIT = 5000  # максимум строк в результате ответа
OP_LIMIT = 200_000  # лимит операций sqlite на один запрос (антизависание)
FLOAT_TOL = 1e-6

_DEPTS = ["Разработка", "Тестирование", "Аналитика", "Поддержка", "Маркетинг", "Продажи"]
_NAMES = ["Анна", "Борис", "Вера", "Гриша", "Даша", "Егор", "Жанна", "Иван", "Кира",
          "Лев", "Мая", "Никита", "Ольга", "Пётр", "Рита", "Семён", "Тая", "Ульяна"]
_CITIES = ["Москва", "Казань", "Пермь", "Тверь", "Сочи", "Омск"]
_ORDER_STATUS = ["paid", "shipped", "pending", "cancelled"]
_FACULTIES = ["ИТ", "Математика", "Физика", "Экономика"]
_COURSES = ["Алгоритмы", "Базы данных", "Сети", "Анализ", "Программирование", "Статистика"]


@dataclass
class DomainData:
    setup_sql: str
    schema: str  # человекочитаемое описание схемы
    values: dict[str, Any]  # сгенерированные строки (для паттернов)


# ------------------------------------------------------------------ домены


def _gen_employees(rng: random.Random) -> DomainData:
    dept_names = rng.sample(_DEPTS, 4)
    departments = [(i + 1, name) for i, name in enumerate(dept_names)]
    n = rng.randint(8, 11)
    names = rng.sample(_NAMES, n)
    salaries = rng.sample(range(40, 221), n)  # различные — однозначный ROW_NUMBER
    employees = [
        (i + 1, names[i], rng.choice([d[0] for d in departments]), salaries[i],
         rng.randint(2018, 2025))
        for i in range(n)
    ]
    ddl = (
        "CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT);\n"
        "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER "
        "REFERENCES departments(id), salary INTEGER, hired_year INTEGER);\n"
    )
    inserts = "".join(
        f"INSERT INTO departments VALUES ({d[0]}, '{d[1]}');\n" for d in departments
    )
    inserts += "".join(
        f"INSERT INTO employees VALUES ({e[0]}, '{e[1]}', {e[2]}, {e[3]}, {e[4]});\n"
        for e in employees
    )
    schema = (
        "departments(id, name) — отделы;\n"
        "employees(id, name, dept_id → departments.id, salary, hired_year) — сотрудники, "
        "зарплата в тыс. руб."
    )
    return DomainData(
        setup_sql=ddl + inserts,
        schema=schema,
        values={"departments": departments, "employees": employees},
    )


def _gen_orders(rng: random.Random) -> DomainData:
    n_cust = rng.randint(5, 6)
    names = rng.sample(_NAMES, n_cust)
    cities = rng.sample(_CITIES, 3)
    customers = [(i + 1, names[i], rng.choice(cities)) for i in range(n_cust)]
    n = rng.randint(10, 14)
    amounts = rng.sample(range(5, 300), n)  # различные, ×100 руб.
    orders = [
        (i + 1, rng.choice([c[0] for c in customers]), amounts[i] * 100,
         rng.choice(_ORDER_STATUS), rng.randint(2023, 2025))
        for i in range(n)
    ]
    ddl = (
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT);\n"
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER "
        "REFERENCES customers(id), amount INTEGER, status TEXT, created_year INTEGER);\n"
    )
    inserts = "".join(
        f"INSERT INTO customers VALUES ({c[0]}, '{c[1]}', '{c[2]}');\n" for c in customers
    )
    inserts += "".join(
        f"INSERT INTO orders VALUES ({o[0]}, {o[1]}, {o[2]}, '{o[3]}', {o[4]});\n"
        for o in orders
    )
    schema = (
        "customers(id, name, city) — клиенты;\n"
        "orders(id, customer_id → customers.id, amount, status, created_year) — заказы, "
        "сумма в рублях."
    )
    return DomainData(
        setup_sql=ddl + inserts,
        schema=schema,
        values={"customers": customers, "orders": orders},
    )


def _gen_students(rng: random.Random) -> DomainData:
    n_st = rng.randint(6, 8)
    names = rng.sample(_NAMES, n_st)
    students = [(i + 1, names[i], rng.choice(_FACULTIES)) for i in range(n_st)]
    courses = rng.sample(_COURSES, 4)
    n = rng.randint(10, 16)
    scores = rng.sample(range(40, 101), n)  # различные — однозначный ROW_NUMBER
    enrollments = [
        (i + 1, rng.choice([s[0] for s in students]), rng.choice(courses), scores[i])
        for i in range(n)
    ]
    ddl = (
        "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, faculty TEXT);\n"
        "CREATE TABLE enrollments (id INTEGER PRIMARY KEY, student_id INTEGER "
        "REFERENCES students(id), course TEXT, score INTEGER);\n"
    )
    inserts = "".join(
        f"INSERT INTO students VALUES ({s[0]}, '{s[1]}', '{s[2]}');\n" for s in students
    )
    inserts += "".join(
        f"INSERT INTO enrollments VALUES ({e[0]}, {e[1]}, '{e[2]}', {e[3]});\n"
        for e in enrollments
    )
    schema = (
        "students(id, name, faculty) — студенты;\n"
        "enrollments(id, student_id → students.id, course, score) — записи на курсы "
        "с оценкой (0–100)."
    )
    return DomainData(
        setup_sql=ddl + inserts,
        schema=schema,
        values={"students": students, "enrollments": enrollments},
    )


DOMAINS: dict[str, Callable[[random.Random], DomainData]] = {
    "employees": _gen_employees,
    "orders": _gen_orders,
    "students": _gen_students,
}


# ------------------------------------------------------------- исполнение SQL


def run_query(setup_sql: str, query: str) -> list[tuple]:
    """Выполняет одиночный запрос на свежей in-memory БД с лимитом операций."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup_sql)
        ops = 0

        def _progress() -> int:
            nonlocal ops
            ops += 1
            return 1 if ops > OP_LIMIT else 0

        conn.set_progress_handler(_progress, 100)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchmany(ROW_LIMIT + 1)
        if len(rows) > ROW_LIMIT:
            raise ValueError(f"результат больше {ROW_LIMIT} строк")
        return [tuple(r) for r in rows]
    finally:
        conn.close()


def _norm_value(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 6)
    return v


def same_multiset(expected: list[tuple], got: list[tuple]) -> bool:
    """Сравнение мультимножеств строк без учёта порядка; float — с округлением."""
    norm = lambda rows: Counter(tuple(_norm_value(v) for v in row) for row in rows)  # noqa: E731
    return norm(expected) == norm(got)


def _make_checker(setup_sql: str, expected: list[tuple]) -> Callable[[Any], bool]:
    def check(answer: Any) -> bool:
        if not isinstance(answer, str) or not answer.strip():
            return False
        try:
            got = run_query(setup_sql, answer)
        except Exception:
            return False
        return same_multiset(expected, got)

    return check


# ----------------------------------------------------------------- паттерны


@dataclass
class SqlParts:
    question: str
    ref_sql: str
    columns: list[str]


def _p_join_group_having(domain: str, opts: dict, data: DomainData) -> SqlParts | None:
    thr = int(opts["thr"])
    if domain == "employees":
        ref = (
            "SELECT d.name, COUNT(e.id) AS cnt FROM employees e "
            "JOIN departments d ON d.id = e.dept_id "
            f"GROUP BY d.name HAVING COUNT(e.id) >= {thr}"
        )
        question = (
            f"Для каждого отдела посчитайте число сотрудников и оставьте только отделы, "
            f"где сотрудников не меньше {thr}. Колонки результата: name, cnt."
        )
        columns = ["name", "cnt"]
    elif domain == "orders":
        ref = (
            "SELECT c.name, COUNT(o.id) AS cnt FROM customers c "
            "JOIN orders o ON o.customer_id = c.id "
            f"GROUP BY c.name HAVING COUNT(o.id) >= {thr}"
        )
        question = (
            f"Для каждого клиента посчитайте число заказов и оставьте только клиентов "
            f"с числом заказов не меньше {thr}. Колонки результата: name, cnt."
        )
        columns = ["name", "cnt"]
    else:
        ref = (
            "SELECT e.course, COUNT(e.id) AS cnt FROM enrollments e "
            f"GROUP BY e.course HAVING COUNT(e.id) >= {thr}"
        )
        question = (
            f"Для каждого курса посчитайте число записавшихся студентов и оставьте "
            f"только курсы с числом записей не меньше {thr}. Колонки результата: course, cnt."
        )
        columns = ["course", "cnt"]
    return SqlParts(question=question, ref_sql=ref, columns=columns)


def _p_subquery_agg(domain: str, opts: dict, data: DomainData) -> SqlParts | None:
    cmp = opts["cmp"]
    word = "выше" if cmp == ">" else "ниже"
    if domain == "employees":
        ref = (
            "SELECT name, salary FROM employees "
            f"WHERE salary {cmp} (SELECT AVG(salary) FROM employees)"
        )
        question = (
            f"Выведите имя и зарплату сотрудников, чья зарплата {word} средней "
            f"по компании. Колонки результата: name, salary."
        )
        columns = ["name", "salary"]
    elif domain == "orders":
        ref = (
            "SELECT DISTINCT c.name FROM customers c "
            "JOIN orders o ON o.customer_id = c.id "
            f"WHERE o.amount {cmp} (SELECT AVG(amount) FROM orders)"
        )
        question = (
            f"Выведите имена клиентов (без повторов), у которых есть заказ на сумму "
            f"{word} средней по всем заказам. Колонки результата: name."
        )
        columns = ["name"]
    else:
        ref = (
            "SELECT s.name, e.score FROM students s "
            "JOIN enrollments e ON e.student_id = s.id "
            f"WHERE e.score {cmp} (SELECT AVG(score) FROM enrollments)"
        )
        question = (
            f"Выведите имя студента и его оценку для всех записей на курсы, где оценка "
            f"{word} средней по всем записям. Колонки результата: name, score."
        )
        columns = ["name", "score"]
    return SqlParts(question=question, ref_sql=ref, columns=columns)


def _p_having_vs_global(domain: str, opts: dict, data: DomainData) -> SqlParts | None:
    if domain == "employees":
        ref = (
            "SELECT d.name, AVG(e.salary) AS avg_salary FROM employees e "
            "JOIN departments d ON d.id = e.dept_id "
            "GROUP BY d.name HAVING AVG(e.salary) > (SELECT AVG(salary) FROM employees)"
        )
        question = (
            "Выведите отделы, где средняя зарплата выше средней по всей компании, "
            "вместе со значением средней. Колонки результата: name, avg_salary."
        )
        columns = ["name", "avg_salary"]
    elif domain == "orders":
        ref = (
            "SELECT c.name, AVG(o.amount) AS avg_amount FROM customers c "
            "JOIN orders o ON o.customer_id = c.id "
            "GROUP BY c.name HAVING AVG(o.amount) > (SELECT AVG(amount) FROM orders)"
        )
        question = (
            "Выведите клиентов, средняя сумма заказа которых выше средней по всем "
            "заказам, вместе со значением средней. Колонки результата: name, avg_amount."
        )
        columns = ["name", "avg_amount"]
    else:
        ref = (
            "SELECT e.course, AVG(e.score) AS avg_score FROM enrollments e "
            "GROUP BY e.course HAVING AVG(e.score) > (SELECT AVG(score) FROM enrollments)"
        )
        question = (
            "Выведите курсы, средний балл по которым выше среднего по всем записям, "
            "вместе со значением среднего. Колонки результата: course, avg_score."
        )
        columns = ["course", "avg_score"]
    return SqlParts(question=question, ref_sql=ref, columns=columns)


def _p_window_top(domain: str, opts: dict, data: DomainData) -> SqlParts | None:
    if domain == "employees":
        ref = (
            "SELECT name, dept, salary FROM ("
            "SELECT e.name AS name, d.name AS dept, e.salary AS salary, "
            "ROW_NUMBER() OVER (PARTITION BY e.dept_id ORDER BY e.salary DESC) AS rn "
            "FROM employees e JOIN departments d ON d.id = e.dept_id"
            ") WHERE rn = 1"
        )
        question = (
            "Для каждого отдела найдите сотрудника с максимальной зарплатой "
            "(зарплаты не повторяются). Колонки результата: name, dept, salary."
        )
        columns = ["name", "dept", "salary"]
    elif domain == "orders":
        ref = (
            "SELECT name, amount FROM ("
            "SELECT c.name AS name, o.amount AS amount, "
            "ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.amount DESC) AS rn "
            "FROM orders o JOIN customers c ON c.id = o.customer_id"
            ") WHERE rn = 1"
        )
        question = (
            "Для каждого клиента найдите его максимальный заказ "
            "(суммы не повторяются). Колонки результата: name, amount."
        )
        columns = ["name", "amount"]
    else:
        ref = (
            "SELECT name, course, score FROM ("
            "SELECT s.name AS name, e.course AS course, e.score AS score, "
            "ROW_NUMBER() OVER (PARTITION BY e.course ORDER BY e.score DESC) AS rn "
            "FROM enrollments e JOIN students s ON s.id = e.student_id"
            ") WHERE rn = 1"
        )
        question = (
            "Для каждого курса найдите студента с лучшей оценкой "
            "(оценки не повторяются). Колонки результата: name, course, score."
        )
        columns = ["name", "course", "score"]
    return SqlParts(question=question, ref_sql=ref, columns=columns)


PATTERNS: dict[str, Callable[[str, dict, DomainData], SqlParts | None]] = {
    "join_group_having": _p_join_group_having,
    "subquery_agg": _p_subquery_agg,
    "having_vs_global": _p_having_vs_global,
    "window_top": _p_window_top,
}

PATTERN_CYCLE = ("join_group_having", "subquery_agg", "having_vs_global", "window_top")
DOMAIN_CYCLE = ("employees", "orders", "students")

# Эвристика β по паттерну/домену (уточняется BetaStat по истории ответов).
_BETA: dict[tuple[str, str], float] = {
    ("join_group_having", "employees"): 0.2,
    ("join_group_having", "orders"): 0.2,
    ("join_group_having", "students"): 0.1,
    ("subquery_agg", "employees"): 0.7,
    ("subquery_agg", "orders"): 0.9,  # + JOIN и DISTINCT
    ("subquery_agg", "students"): 0.8,
    ("having_vs_global", "employees"): 1.3,
    ("having_vs_global", "orders"): 1.3,
    ("having_vs_global", "students"): 1.2,
    ("window_top", "employees"): 1.9,
    ("window_top", "orders"): 2.0,
    ("window_top", "students"): 1.8,
}


def _opts_for(pattern: str, crng: random.Random) -> dict:
    if pattern == "join_group_having":
        return {"thr": crng.randint(2, 3)}
    if pattern == "subquery_agg":
        return {"cmp": crng.choice([">", "<"])}
    return {}


def _beta_for(pattern: str, domain: str, opts: dict) -> float:
    beta = _BETA[(pattern, domain)]
    if pattern == "join_group_having":
        beta += 0.1 * (int(opts["thr"]) - 2)
    return beta


# ---------------------------------------------------------------- сборка шаблона


def build_generator(template: ItemTemplate) -> Callable[[int], Instance]:
    """Восстанавливает instantiate(seed) из params шаблона (domain + pattern + opts)."""
    domain = template.params["domain"]
    pattern = template.params["pattern"]
    opts = template.params["opts"]
    gen_data = DOMAINS[domain]
    pattern_fn = PATTERNS[pattern]

    def instantiate(seed: int) -> Instance:
        base = f"{template.id}#{seed}"
        for attempt in range(_MAX_ATTEMPTS):
            rng = random.Random(f"{base}#{attempt}")
            data = gen_data(rng)
            parts = pattern_fn(domain, opts, data)
            if parts is None:
                continue
            try:
                expected = run_query(data.setup_sql, parts.ref_sql)
            except Exception:
                continue
            if not expected:  # эталон обязан быть непустым (иначе задание вырождается)
                continue
            question = (
                "Напишите SQL-запрос (sqlite).\n\n"
                f"Схема:\n{data.schema}\n\n"
                f"{parts.question}\n\n"
                "Порядок строк при проверке не учитывается."
            )
            return Instance(
                template_id=template.id,
                seed=seed,
                kind="sql",
                topic=template.topic,
                beta=template.beta,
                question_text=question,
                payload={
                    "setup_sql": data.setup_sql,
                    "schema": data.schema,
                    "columns": parts.columns,
                },
                reference=parts.ref_sql,
                checker=_make_checker(data.setup_sql, expected),
                time_limit_s=TIME_LIMITS["sql"],
            )
        raise ItemGenerationError(f"шаблон {template.id}: не удалось сгенерировать seed={seed}")

    return instantiate


def _probe(domain: str, pattern: str, opts: dict, template_id: str,
           probes: tuple[int, ...] = (101, 202, 303)) -> bool:
    probe = ItemTemplate(
        id=template_id, spec="-", topic="-", grade_band="-", kind="sql",
        beta=0.0, factory_id=FACTORY_ID,
        params={"domain": domain, "pattern": pattern, "opts": opts},
    )
    gen = build_generator(probe)
    try:
        for seed in probes:
            gen(seed)
    except Exception:
        return False
    return True


def make_templates(
    spec: str, topic: str, n: int, rng: random.Random, id_prefix: str | None = None
) -> list[ItemTemplate]:
    """Генерирует n sql-шаблонов темы: паттерны по циклу сложности, домены ротируются."""
    prefix = id_prefix or f"sql.{spec}.{topic}"
    # crc32 вместо hash(): hash() строк рандомизирован между процессами (PYTHONHASHSEED)
    offset = zlib.crc32(f"{spec}:{topic}".encode()) % len(PATTERN_CYCLE)
    templates: list[ItemTemplate] = []
    for i in range(n):
        pattern = PATTERN_CYCLE[(offset + i) % len(PATTERN_CYCLE)]
        domain = DOMAIN_CYCLE[(i // len(PATTERN_CYCLE) + i) % len(DOMAIN_CYCLE)]
        tid = f"{prefix}.{i:03d}"
        for _ in range(30):
            opts = _opts_for(pattern, rng)
            if _probe(domain, pattern, opts, tid):
                break
        else:
            continue
        from engine.irt import BETA_HI, BETA_LO

        beta = round(min(BETA_HI, max(BETA_LO, _beta_for(pattern, domain, opts))), 2)
        template = ItemTemplate(
            id=tid,
            spec=spec,
            topic=topic,
            grade_band=grade_for_theta(beta).slug,
            kind="sql",
            beta=beta,
            factory_id=FACTORY_ID,
            params={"domain": domain, "pattern": pattern, "opts": opts},
        )
        template.instantiate = build_generator(template)
        templates.append(template)
    return templates


register_factory(FACTORY_ID, build_generator)
