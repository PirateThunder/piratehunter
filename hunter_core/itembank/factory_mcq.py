"""Фабрика mcq-шаблонов «что выведет код» (PRD §7.4.1, фабрики).

Мета-генератор: собирает случайный безопасный фрагмент Python по грамматике
(списки, срезы, list/dict/set comprehension, zip/enumerate, sorted с
key/lambda, str-методы, арифметика, range), вычисляет эталонный вывод
интерпретатором в изолированном namespace (whitelist builtins, без импортов,
SIGALRM-таймаут; циклы только по материализованным коллекциям) и строит
дистракторы из типовых ошибок: off-by-one в срезе, потерянный фильтр, другой
порядок, другой тип результата, соседнее значение.

Шаблон = семейство + зафиксированная структура (opts, JSON-сериализуема);
instantiate(seed) варьирует только литералы → экземпляры уникальны, сложность
постоянна. β — эвристика из семейства и числа операций (уточняется BetaStat).
"""

from __future__ import annotations

import builtins
import contextlib
import io
import random
import signal
import threading
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from engine.catalog import grade_for_theta
from itembank.model import TIME_LIMITS, Instance, ItemGenerationError, ItemTemplate
from itembank.registry import register_factory

FACTORY_ID = "mcq"

_SAFE_NAMES = (
    "range len list dict set tuple sorted zip enumerate str int float sum min max abs "
    "bool print reversed map filter any all round chr ord"
)
SAFE_BUILTINS = {name: getattr(builtins, name) for name in _SAFE_NAMES.split()}

EXEC_TIMEOUT_S = 2.0
_MAX_ATTEMPTS = 12  # попыток перегенерации литералов внутри instantiate

_WORDS = [
    "python", "django", "server", "docker", "query", "cache", "token", "module",
    "backend", "script", "import", "lambda", "fastapi", "celery", "redis", "kafka",
    "vector", "matrix", "socket", "thread", "parser", "schema", "index", "broker",
    "deploy", "gitlab", "metric", "sentry", "nginx", "postgres", "sqlite", "gunicorn",
    "ansible", "vagrant", "jupyter", "pandas", "numpy", "pytest", "flask", "tornado",
]
_KEY_POOL = ["alpha", "beta", "gamma", "delta", "omega", "sigma", "theta", "kappa"]


class _ExecTimeout(Exception):
    pass


def run_code(code: str, timeout: float = EXEC_TIMEOUT_S) -> tuple[str, dict[str, Any]]:
    """Выполняет код в изолированном namespace; возвращает (stdout, env)."""
    buf = io.StringIO()
    env: dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
    use_alarm = threading.current_thread() is threading.main_thread() and hasattr(
        signal, "setitimer"
    )
    old_handler = None
    if use_alarm:
        def _raise(_signum: int, _frame: Any) -> None:
            raise _ExecTimeout

        old_handler = signal.signal(signal.SIGALRM, _raise)
        signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<mcq-item>", "exec"), env)  # noqa: S102 — sandbox по whitelist
    finally:
        if use_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
    return buf.getvalue().strip(), env


@dataclass
class GenOut:
    code: str
    correct: str  # печатная форма эталонного результата
    distractors: list[str]  # печатные формы, уникальны и ≠ correct


def _printed(value: Any) -> str:
    return str(value)


def _mutate_value(value: Any, rng: random.Random) -> list[Any]:
    """Типовые мутации результата: соседние значения, другой порядок, другой тип."""
    out: list[Any] = []
    if isinstance(value, bool):
        out = [not value]
    elif isinstance(value, int):
        out = [value + 1, value - 1, value * 2, value + 10]
    elif isinstance(value, float):
        out = [value + 1, value - 1, round(value)]
    elif isinstance(value, str):
        cand = [value[::-1], value[1:], value + value[:1]]
        cand.append(value.lower() if value != value.lower() else value.upper())
        out = cand
    elif isinstance(value, list):
        if value:
            out += [list(reversed(value)), value[1:], value[:-1]]
            last = value[-1]
            if isinstance(last, int) and not isinstance(last, bool):
                out.append(value[:-1] + [last + 1])
            if all(isinstance(x, int) and not isinstance(x, bool) for x in value):
                out.append(sum(value))
        out.append(tuple(value))
    elif isinstance(value, tuple):
        out = [list(value), tuple(reversed(value))]
    rng.shuffle(out)
    return out


def _exec_variants(variant_codes: list[str], exclude: set[str]) -> list[str]:
    """Печатные формы вариантов кода (семантические дистракторы)."""
    found: list[str] = []
    for vcode in variant_codes:
        try:
            out, _ = run_code(vcode)
        except Exception:
            continue
        if out and out not in exclude and out not in found:
            found.append(out)
    return found


def _assemble(code: str, res_value: Any, correct: str, variant_codes: list[str],
              rng: random.Random) -> GenOut | None:
    """Собирает эталон + ≥3 уникальных дистрактора (варианты кода, затем мутации)."""
    exclude = {correct}
    distractors = _exec_variants(variant_codes, exclude)
    if len(distractors) < 3:
        for mutated in _mutate_value(res_value, rng):
            text = _printed(mutated)
            if text not in exclude and text not in distractors:
                distractors.append(text)
            if len(distractors) >= 3:
                break
    if len(distractors) < 3:
        return None
    return GenOut(code=code, correct=correct, distractors=distractors[:3])


# ---------------------------------------------------------------- семьи заданий


def _fam_range_slice(opts: dict, rng: random.Random) -> GenOut | None:
    with_step = bool(opts["with_step"])
    kind = opts["slice_kind"]
    a = rng.randint(0, 9)
    n = rng.randint(5, 9)
    st = rng.choice([2, 3]) if with_step else 1
    stop = a + st * n
    rng_call = f"range({a}, {stop})" if st == 1 else f"range({a}, {stop}, {st})"
    if kind == "middle":
        i = rng.randint(1, 3)
        j = i + rng.randint(2, 4)
        sl, var_sl = f"{i}:{j}", [f"{i}:{j + 1}", f"{i - 1}:{j}"]
    elif kind == "tail":
        k = rng.randint(2, 4)
        sl, var_sl = f"-{k}:", [f"-{k + 1}:", f"-{k}:-1"]
    elif kind == "head":
        k = rng.randint(2, 5)
        sl, var_sl = f":{k}", [f":{k + 1}", f"1:{k + 1}"]
    elif kind == "reverse":
        sl, var_sl = "::-1", [None, "::-2"]  # None → res = data (забыли разворот)
    else:  # step
        sl, var_sl = "::2", ["1::2", "::3"]
    code = f"data = list({rng_call})\nres = data[{sl}]\nprint(res)"
    variants = []
    for v in var_sl:
        expr = "data" if v is None else f"data[{v}]"
        variants.append(f"data = list({rng_call})\nres = {expr}\nprint(res)")
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct:
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_range_slice(crng: random.Random) -> dict:
    return {
        "with_step": crng.random() < 0.4,
        "slice_kind": crng.choice(["middle", "tail", "head", "reverse", "step"]),
    }


def _beta_range_slice(opts: dict) -> float:
    beta = -2.0
    if opts["with_step"]:
        beta += 0.3
    if opts["slice_kind"] in ("reverse", "step"):
        beta += 0.2
    if opts["slice_kind"] == "middle":
        beta += 0.1
    return beta


def _fam_str_chain(opts: dict, rng: random.Random) -> GenOut | None:
    methods = opts["methods"]
    use_slice = bool(opts["slice"])
    word = rng.choice(_WORDS)
    if rng.random() < 0.5:  # составное слово: вторая литеральная размерность seed'а
        word += rng.choice(["-", "_"]) + rng.choice(_WORDS)
    expr = "s"
    val = word
    # replace-пары подбираем по реальному тексту: буква-источник обязана
    # присутствовать в текущем значении, иначе цепочка вырождается в исходное
    # слово (слова без нужной буквы давали «пустые» экземпляры).
    resolved: list[list] = []
    for m in methods:
        if m[0] == "replace":
            letters = sorted({c for c in val if c.isalpha()})
            if not letters:
                return None
            a = rng.choice(letters)
            b = rng.choice("aeiou")
            if a.isupper():
                b = b.upper()
            if b == a:
                b = "Q" if a.isupper() else "q"
            resolved.append(["replace", a, b])
            expr += f".replace({a!r}, {b!r})"
            val = val.replace(a, b)
        else:
            resolved.append([m[0]])
            expr += f".{m[0]}()"
            val = getattr(val, m[0])()
    if use_slice:
        i = rng.randint(0, 2)
        j = i + rng.randint(2, 4)
        expr += f"[{i}:{j}]"
        val = val[i:j]
    if not val or val == word:
        return None
    code = f's = "{word}"\nres = {expr}\nprint(res)'
    variants: list[str] = []
    if len(resolved) > 1:
        sub = "s"
        for m in resolved[1:]:
            args = ", ".join(repr(a) for a in m[1:])
            sub += f".{m[0]}({args})"
        variants.append(f's = "{word}"\nres = {sub}\nprint(res)')
    if use_slice:
        variants.append(f's = "{word}"\nres = {expr[: expr.rindex("[")]}\nprint(res)')
    for m in resolved:
        if m[0] == "replace":
            swapped = expr.replace(f"{m[1]!r}, {m[2]!r}", f"{m[2]!r}, {m[1]!r}")
            if swapped != expr:
                variants.append(f's = "{word}"\nres = {swapped}\nprint(res)')
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct or correct == word:
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_str_chain(crng: random.Random) -> dict:
    n = crng.randint(1, 3)
    methods = [[crng.choice(["upper", "lower", "title", "replace", "capitalize"])]
               for _ in range(n)]
    # одиночный метод без среза даёт мало комбинаций литералов — режимим
    return {"methods": methods, "slice": True if n == 1 else crng.random() < 0.6}


def _beta_str_chain(opts: dict) -> float:
    return -1.6 + 0.25 * (len(opts["methods"]) - 1) + (0.3 if opts["slice"] else 0.0)


def _fam_filter_map(opts: dict, rng: random.Random) -> GenOut | None:
    op = opts["op"]
    square = bool(opts["square"])
    data = rng.sample(range(1, 13), k=rng.randint(5, 6))
    m = rng.choice([2, 3])
    r = rng.randrange(m)
    k = rng.randint(2, 4) if op == "*" else rng.randint(1, 9)
    expr = "x * x" if square else f"x {op} {k}"
    matches = [x for x in data if x % m == r]
    if not matches or len(matches) == len(data):
        return None
    code = f"data = {data}\nres = [{expr} for x in data if x % {m} == {r}]\nprint(res)"
    plain = "x * x" if square else f"x {op} {k}"
    variants = [
        f"data = {data}\nres = [{plain} for x in data]\nprint(res)",
        f"data = {data}\nres = [{plain} for x in data if x % {m} == {(r + 1) % m}]\nprint(res)",
    ]
    if square:
        variants.append(
            f"data = {data}\nres = [x + {k} for x in data if x % {m} == {r}]\nprint(res)"
        )
    else:
        variants.append(
            f"data = {data}\nres = [x {op} {k + 1} for x in data if x % {m} == {r}]\nprint(res)"
        )
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct:
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_filter_map(crng: random.Random) -> dict:
    return {"op": crng.choice(["*", "+", "-"]), "square": crng.random() < 0.3}


def _beta_filter_map(opts: dict) -> float:
    return -0.8 + (0.2 if opts["square"] else 0.0)


def _fam_enum_acc(opts: dict, rng: random.Random) -> GenOut | None:
    start = int(opts["start"])
    op = opts["op"]
    cond = opts["cond"]
    data = [rng.randint(1, 9) for _ in range(rng.randint(5, 6))]
    init = rng.randint(1, 2) if op == "*" else rng.randint(0, 2)
    enum_args = "data, 1" if start else "data"
    head = f"data = {data}\nacc = {init}\nfor i, x in enumerate({enum_args}):\n"
    if cond == "every":
        code = head + f"    acc {op}= x\nprint(acc)"
    else:
        parity = 0 if cond == "even" else 1
        code = head + f"    if i % 2 == {parity}:\n        acc {op}= x\nprint(acc)"
    variants: list[str] = []
    other_args = "data" if start else "data, 1"
    other_head = f"data = {data}\nacc = {init}\nfor i, x in enumerate({other_args}):\n"
    if cond == "every":
        variants.append(other_head + f"    acc {op}= x\nprint(acc)")
    else:
        parity = 0 if cond == "even" else 1
        variants.append(
            head + f"    if i % 2 == {1 - parity}:\n        acc {op}= x\nprint(acc)"
        )
        variants.append(other_head + f"    if i % 2 == {parity}:\n        acc {op}= x\nprint(acc)")
    variants.append(
        f"data = {data}\nacc = {init + 1}\nfor i, x in enumerate({enum_args}):\n"
        + (f"    acc {op}= x\nprint(acc)" if cond == "every"
           else f"    if i % 2 == {0 if cond == 'even' else 1}:\n        acc {op}= x\nprint(acc)")
    )
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct or correct == str(init):
        return None
    return _assemble(code, env["acc"], correct, variants, rng)


def _opts_enum_acc(crng: random.Random) -> dict:
    return {
        "start": crng.randint(0, 1),
        "op": crng.choice(["+", "*"]),
        "cond": crng.choice(["even", "odd", "every"]),
    }


def _beta_enum_acc(opts: dict) -> float:
    beta = -0.2
    if opts["cond"] != "every":
        beta += 0.3
    if opts["start"]:
        beta += 0.2
    return beta


def _fam_zip_dict(opts: dict, rng: random.Random) -> GenOut | None:
    op = opts["op"]
    sel = opts["sel"]
    nk = rng.randint(3, 4)
    keys = rng.sample(_KEY_POOL, nk)
    vals = [rng.randint(1, 9) for _ in range(nk)]
    c = rng.randint(1, 3)
    expr = f"v {op} {c}"
    head = f"keys = {keys}\nvals = {vals}\nd = {{k: {expr} for k, v in zip(keys, vals)}}\n"
    if sel == "key":
        pick = rng.choice(keys)
        tail = f'd["{pick}"]'
        alt_tail = f'd["{rng.choice([k2 for k2 in keys if k2 != pick])}"]'
    elif sel == "get":
        tail = f'd.get("zeta", {c})'
        alt_tail = f'd["{rng.choice(keys)}"]'
    else:
        tail = "sorted(d.items())"
        alt_tail = "sorted(d)"
    code = head + f"res = {tail}\nprint(res)"
    plain_head = f"keys = {keys}\nvals = {vals}\nd = {{k: v for k, v in zip(keys, vals)}}\n"
    variants = [plain_head + f"res = {tail}\nprint(res)", head + f"res = {alt_tail}\nprint(res)"]
    if sel != "items":
        variants.append(head + "res = sum(d.values())\nprint(res)")
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct:
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_zip_dict(crng: random.Random) -> dict:
    return {
        "op": crng.choice(["+", "*"]),
        "sel": crng.choice(["key", "get", "items"]),
    }


def _beta_zip_dict(_opts: dict) -> float:
    return 0.5


def _fam_sorted_lambda(opts: dict, rng: random.Random) -> GenOut | None:
    key_idx = int(opts["key_idx"])
    reverse = bool(opts["reverse"])
    pick = opts["pick"]
    for _ in range(20):
        pairs = [(rng.randint(1, 25), rng.randint(1, 25)) for _ in range(4)]
        if len({p[key_idx] for p in pairs}) == 4:
            break
    else:
        return None
    rev = ", reverse=True" if reverse else ""
    base = f"sorted(data, key=lambda t: t[{key_idx}]{rev})"
    tail = {"all": base, "first": f"{base}[0]", "last": f"{base}[-1]"}[pick]
    code = f"data = {pairs}\nres = {tail}\nprint(res)"
    other = 1 - key_idx
    base_other = f"sorted(data, key=lambda t: t[{other}]{rev})"
    rev_flip = "" if reverse else ", reverse=True"
    base_flip = f"sorted(data, key=lambda t: t[{key_idx}]{rev_flip})"
    variants = [
        f"data = {pairs}\nres = {base_other}\nprint(res)",
        f"data = {pairs}\nres = {base_flip}\nprint(res)",
    ]
    if pick == "first":
        variants.append(f"data = {pairs}\nres = {base}[-1]\nprint(res)")
    elif pick == "last":
        variants.append(f"data = {pairs}\nres = {base}[0]\nprint(res)")
    else:
        variants.append(f"data = {pairs}\nres = {base}[1]\nprint(res)")
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct:
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_sorted_lambda(crng: random.Random) -> dict:
    return {
        "key_idx": crng.randint(0, 1),
        "reverse": crng.random() < 0.5,
        "pick": crng.choice(["all", "first", "last"]),
    }


def _beta_sorted_lambda(opts: dict) -> float:
    beta = 0.9
    if opts["reverse"]:
        beta += 0.2
    if opts["pick"] != "all":
        beta += 0.2
    return beta


def _fam_nested_set(opts: dict, rng: random.Random) -> GenOut | None:
    kind = opts["kind"]
    if kind == "flat":
        m = rng.choice([2, 3])
        r = rng.randrange(m)
        rows = [[rng.randint(1, 12) for _ in range(rng.randint(2, 3))] for _ in range(2)]
        if len(rows) < 2:
            return None
        dup = r + m * rng.randint(1, 3)  # дубликат, проходящий фильтр: set ≠ list
        rows[0][0] = dup
        rows[1][0] = dup
        if not any(x % m == r for row in rows for x in row):
            return None
        code = (
            f"rows = {rows}\n"
            f"res = sorted({{x for row in rows for x in row if x % {m} == {r}}})\n"
            "print(res)"
        )
        variants = [
            f"rows = {rows}\nres = sorted([x for row in rows for x in row "
            f"if x % {m} == {r}])\nprint(res)",
            f"rows = {rows}\nres = sorted({{x for row in rows for x in row}})\nprint(res)",
            f"rows = {rows}\nres = {{x for row in rows for x in row "
            f"if x % {m} == {r}}}\nprint(res)",
        ]
        try:
            correct, env = run_code(code)
        except Exception:
            return None
        if not correct or correct == "[]":
            return None
        return _assemble(code, env["res"], correct, variants, rng)
    nk = rng.randint(3, 4)
    keys = rng.sample(_KEY_POOL, nk)
    vals = rng.sample(range(10, 60), nk)
    pick = rng.choice(vals)
    head = f"keys = {keys}\nvals = {vals}\nd = {{v: k for k, v in zip(keys, vals)}}\n"
    code = head + f"res = d[{pick}]\nprint(res)"
    straight = f"keys = {keys}\nvals = {vals}\nd = {{k: v for k, v in zip(keys, vals)}}\n"
    key_at = keys[vals.index(pick)]
    other = rng.choice([v for v in vals if v != pick])
    variants = [
        straight + f'res = d["{key_at}"]\nprint(res)',
        head + f"res = d[{other}]\nprint(res)",
        head + "res = sorted(d)\nprint(res)",
    ]
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct:
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_nested_set(crng: random.Random) -> dict:
    return {"kind": crng.choice(["flat", "invert"])}


def _beta_nested_set(opts: dict) -> float:
    return 1.7 if opts["kind"] == "flat" else 1.6


def _fam_combo(opts: dict, rng: random.Random) -> GenOut | None:
    m = int(opts["m"])
    key = opts["key"]
    data = [(rng.randint(1, 9), rng.randint(1, 9)) for _ in range(5)]
    r = rng.randrange(m)
    if sum(1 for x, _y in data if x % m == r) < 2:
        return None
    keyexpr = {"first": "t[0]", "second": "t[1]", "neg_second": "-t[1]"}[key]
    code = (
        f"data = {data}\n"
        f"res = [x * y for x, y in sorted(data, key=lambda t: {keyexpr}) "
        f"if x % {m} == {r}][:2]\n"
        "print(res)"
    )
    variants = [
        f"data = {data}\nres = [x * y for x, y in sorted(data, key=lambda t: {keyexpr})][:2]\n"
        "print(res)",
        f"data = {data}\nres = [x * y for x, y in sorted(data, key=lambda t: {keyexpr}) "
        f"if x % {m} == {r}]\nprint(res)",
        f"data = {data}\nres = [x * y for x, y in sorted(data) if x % {m} == {r}][:2]\nprint(res)",
        f"data = {data}\nres = [x + y for x, y in sorted(data, key=lambda t: {keyexpr}) "
        f"if x % {m} == {r}][:2]\nprint(res)",
    ]
    try:
        correct, env = run_code(code)
    except Exception:
        return None
    if not correct or correct == "[]":
        return None
    return _assemble(code, env["res"], correct, variants, rng)


def _opts_combo(crng: random.Random) -> dict:
    return {
        "m": crng.choice([2, 3]),
        "key": crng.choice(["first", "second", "neg_second"]),
    }


def _beta_combo(opts: dict) -> float:
    return 2.4 + (0.2 if opts["key"] == "neg_second" else 0.0)


# family -> (генератор экземпляра, билдер opts, эвристика β)
FAMILIES: dict[
    str,
    tuple[
        Callable[[dict, random.Random], GenOut | None],
        Callable[[random.Random], dict],
        Callable[[dict], float],
    ],
] = {
    "range_slice": (_fam_range_slice, _opts_range_slice, _beta_range_slice),
    "str_chain": (_fam_str_chain, _opts_str_chain, _beta_str_chain),
    "filter_map": (_fam_filter_map, _opts_filter_map, _beta_filter_map),
    "enum_acc": (_fam_enum_acc, _opts_enum_acc, _beta_enum_acc),
    "zip_dict": (_fam_zip_dict, _opts_zip_dict, _beta_zip_dict),
    "sorted_lambda": (_fam_sorted_lambda, _opts_sorted_lambda, _beta_sorted_lambda),
    "nested_set": (_fam_nested_set, _opts_nested_set, _beta_nested_set),
    "combo": (_fam_combo, _opts_combo, _beta_combo),
}

# Цикл семейств: покрывает всю лестницу сложности (intern → senior).
FAMILY_CYCLE = (
    "range_slice", "str_chain", "filter_map", "enum_acc",
    "zip_dict", "sorted_lambda", "nested_set", "combo",
)


# ---------------------------------------------------------------- сборка шаблона


def _clamp_beta(beta: float) -> float:
    from engine.irt import BETA_HI, BETA_LO

    return round(min(BETA_HI, max(BETA_LO, beta)), 2)


def _make_checker(options: list[str], correct: str) -> Callable[[Any], bool]:
    def check(answer: Any) -> bool:
        if isinstance(answer, int) and not isinstance(answer, bool):
            return 0 <= answer < len(options) and options[answer] == correct
        return str(answer).strip() == correct

    return check


def build_generator(template: ItemTemplate) -> Callable[[int], Instance]:
    """Восстанавливает instantiate(seed) из params шаблона (family + opts)."""
    family = template.params["family"]
    opts = template.params["opts"]
    gen_fn = FAMILIES[family][0]

    def instantiate(seed: int) -> Instance:
        base = f"{template.id}#{seed}"
        for attempt in range(_MAX_ATTEMPTS):
            rng = random.Random(f"{base}#{attempt}")
            try:
                out = gen_fn(opts, rng)
            except Exception:
                out = None
            if out is None:
                continue
            options = [out.correct, *out.distractors]
            rng.shuffle(options)
            question = (
                "Что выведет этот фрагмент кода на Python?\n\n"
                f"```python\n{out.code}\n```"
            )
            return Instance(
                template_id=template.id,
                seed=seed,
                kind="mcq",
                topic=template.topic,
                beta=template.beta,
                question_text=question,
                payload={"code": out.code, "options": options},
                reference=out.correct,
                checker=_make_checker(options, out.correct),
                time_limit_s=TIME_LIMITS["mcq"],
            )
        raise ItemGenerationError(f"шаблон {template.id}: не удалось сгенерировать seed={seed}")

    return instantiate


def _probe(family: str, opts: dict, template_id: str, probes: tuple[int, ...] = (101, 202)) -> bool:
    probe = ItemTemplate(
        id=template_id, spec="-", topic="-", grade_band="-", kind="mcq",
        beta=0.0, factory_id=FACTORY_ID, params={"family": family, "opts": opts},
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
    """Генерирует n шаблонов темы: семьи идут по циклу сложности, opts — случайны.

    Шаблоны, не прошедшие пробную генерацию (мало дистракторов / ошибки кода),
    перегенерируются с другими opts (до 30 попыток), затем пропускаются.
    """
    prefix = id_prefix or f"mcq.{spec}.{topic}"
    # crc32 вместо hash(): hash() строк рандомизирован между процессами (PYTHONHASHSEED)
    offset = zlib.crc32(f"{spec}:{topic}".encode()) % len(FAMILY_CYCLE)
    templates: list[ItemTemplate] = []
    for i in range(n):
        family = FAMILY_CYCLE[(offset + i) % len(FAMILY_CYCLE)]
        _gen, opts_builder, beta_fn = FAMILIES[family]
        tid = f"{prefix}.{i:03d}"
        for _ in range(30):
            opts = opts_builder(rng)
            if _probe(family, opts, tid):
                break
        else:
            continue
        beta = _clamp_beta(beta_fn(opts))
        template = ItemTemplate(
            id=tid,
            spec=spec,
            topic=topic,
            grade_band=grade_for_theta(beta).slug,
            kind="mcq",
            beta=beta,
            factory_id=FACTORY_ID,
            params={"family": family, "opts": opts},
        )
        template.instantiate = build_generator(template)
        templates.append(template)
    return templates


register_factory(FACTORY_ID, build_generator)
