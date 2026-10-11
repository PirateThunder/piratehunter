"""Справочник специализаций и грейдов (PRD §6).

7 специализаций с русскими названиями и темами, 4 грейда с θ-полосами:
intern < −1 ≤ junior < 0.5 ≤ middle < 2 ≤ senior. Категория кандидата =
spec_slug × grade_verified. Структуры — frozen dataclass'ы, сериализуемы.

MCQ_TOPICS / SQL_TOPICS — маршрутизация тем для фабрик банка заданий:
mcq-фабрика генерирует трейсинг Python (универсальная проверка логики
программирования), поэтому маппится на кодовые темы специализации;
sql-фабрика — на темы SQL/хранилищ. Для тем вне маппинга фабрика не
вызывается (банк по ним — предмет авторской работы, не этой фазы).
"""

from __future__ import annotations

from dataclasses import dataclass

THETA_MIN = -4.0
THETA_MAX = 4.0


@dataclass(frozen=True)
class Topic:
    slug: str
    title: str

    def to_dict(self) -> dict:
        return {"slug": self.slug, "title": self.title}


@dataclass(frozen=True)
class Specialization:
    slug: str
    title: str
    topics: tuple[Topic, ...]

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "topics": [t.to_dict() for t in self.topics],
        }


@dataclass(frozen=True)
class Grade:
    slug: str
    title: str
    lo: float  # нижняя граница θ-полосы, включительно
    hi: float  # верхняя граница, исключительно (у senior — верх шкалы)
    description: str

    @property
    def median(self) -> float:
        return (self.lo + self.hi) / 2

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "lo": self.lo,
            "hi": self.hi,
            "description": self.description,
        }


def _topics(*pairs: tuple[str, str]) -> tuple[Topic, ...]:
    return tuple(Topic(slug, title) for slug, title in pairs)


SPECIALIZATIONS: tuple[Specialization, ...] = (
    Specialization(
        "backend",
        "Бэкенд-разработка",
        _topics(
            ("python", "Python"),
            ("sql", "SQL"),
            ("algorithms", "Алгоритмы и структуры данных"),
            ("api-design", "Проектирование API"),
            ("databases", "Базы данных"),
            ("caching", "Кеширование"),
            ("concurrency", "Конкурентность и асинхронность"),
        ),
    ),
    Specialization(
        "frontend",
        "Фронтенд-разработка",
        _topics(
            ("javascript", "JavaScript"),
            ("typescript", "TypeScript"),
            ("react", "React"),
            ("css", "CSS и вёрстка"),
            ("browser-apis", "API браузера"),
            ("state-management", "Управление состоянием"),
            ("algorithms", "Алгоритмы и логика"),
            ("performance", "Производительность фронтенда"),
        ),
    ),
    Specialization(
        "fullstack",
        "Фулстек-разработка",
        _topics(
            ("python", "Python"),
            ("javascript", "JavaScript"),
            ("sql", "SQL"),
            ("api-design", "Проектирование API"),
            ("react", "React"),
            ("databases", "Базы данных"),
            ("devops-basics", "Основы DevOps"),
        ),
    ),
    Specialization(
        "mobile",
        "Мобильная разработка",
        _topics(
            ("kotlin", "Kotlin"),
            ("swift", "Swift"),
            ("flutter", "Flutter"),
            ("mobile-ui", "Мобильный UI"),
            ("networking", "Сетевое взаимодействие"),
            ("storage", "Локальное хранение"),
            ("algorithms", "Алгоритмы и логика"),
        ),
    ),
    Specialization(
        "qa",
        "Тестирование и QA",
        _topics(
            ("testing-theory", "Теория тестирования"),
            ("test-design", "Тест-дизайн"),
            ("automation", "Автоматизация тестирования"),
            ("python", "Python"),
            ("sql", "SQL"),
            ("api-testing", "Тестирование API"),
            ("ci-cd", "CI/CD"),
        ),
    ),
    Specialization(
        "devops",
        "DevOps и инфраструктура",
        _topics(
            ("linux", "Linux"),
            ("docker", "Docker"),
            ("kubernetes", "Kubernetes"),
            ("ci-cd", "CI/CD"),
            ("networking", "Сети"),
            ("monitoring", "Мониторинг и логирование"),
            ("scripting", "Скриптинг (Bash/Python)"),
        ),
    ),
    Specialization(
        "data-ml",
        "Data / ML",
        _topics(
            ("python", "Python"),
            ("sql", "SQL"),
            ("statistics", "Статистика"),
            ("ml-basics", "Основы ML"),
            ("data-processing", "Обработка данных"),
            ("mlops", "MLOps"),
            ("deep-learning", "Глубокое обучение"),
        ),
    ),
)

GRADES: tuple[Grade, ...] = (
    # Грейд — уровень навыка, подтверждаемый тестом (PRD §6); без привязки к стажу.
    Grade("intern", "Начинающий", THETA_MIN, -1.0, "базовые конструкции и простые задачи"),
    Grade("junior", "Джуниор", -1.0, 0.5, "уверенное владение основами, типовые задачи"),
    Grade("middle", "Мидл", 0.5, 2.0, "нестандартные задачи, системное мышление"),
    Grade("senior", "Сеньор", 2.0, THETA_MAX, "экспертный уровень, граничные случаи"),
)

# Темы, которые обслуживает mcq-фабрика (трейсинг Python) по специализациям.
MCQ_TOPICS: dict[str, tuple[str, ...]] = {
    "backend": ("python", "algorithms", "concurrency"),
    "frontend": ("algorithms",),
    "fullstack": ("python", "algorithms"),
    "mobile": ("algorithms",),
    "qa": ("python", "automation"),
    "devops": ("scripting",),
    "data-ml": ("python",),
}

# Темы, которые обслуживает sql-фабрика.
SQL_TOPICS: dict[str, tuple[str, ...]] = {
    "backend": ("sql", "databases"),
    "frontend": (),
    "fullstack": ("sql", "databases"),
    "mobile": ("storage",),
    "qa": ("sql",),
    "devops": (),
    "data-ml": ("sql",),
}

_SPEC_BY_SLUG = {s.slug: s for s in SPECIALIZATIONS}
_GRADE_BY_SLUG = {g.slug: g for g in GRADES}


def get_specialization(slug: str) -> Specialization:
    try:
        return _SPEC_BY_SLUG[slug]
    except KeyError:
        raise ValueError(f"неизвестная специализация: {slug!r}") from None


def get_grade(slug: str) -> Grade:
    try:
        return _GRADE_BY_SLUG[slug]
    except KeyError:
        raise ValueError(f"неизвестный грейд: {slug!r}") from None


def grade_for_theta(theta: float) -> Grade:
    """Грейд, чья θ-полоса содержит theta (intern < −1 ≤ junior < 0.5 ≤ middle < 2 ≤ senior)."""
    for g in GRADES:
        if g.lo <= theta < g.hi:
            return g
    return GRADES[-1] if theta >= GRADES[-1].lo else GRADES[0]


def grade_index(slug: str) -> int:
    return next(i for i, g in enumerate(GRADES) if g.slug == slug)


def next_grade(slug: str) -> Grade | None:
    i = grade_index(slug)
    return GRADES[i + 1] if i + 1 < len(GRADES) else None


def prev_grade(slug: str) -> Grade | None:
    i = grade_index(slug)
    return GRADES[i - 1] if i > 0 else None


def catalog_dict() -> dict:
    return {
        "specializations": [s.to_dict() for s in SPECIALIZATIONS],
        "grades": [g.to_dict() for g in GRADES],
        "theta_scale": {"min": THETA_MIN, "max": THETA_MAX},
    }
