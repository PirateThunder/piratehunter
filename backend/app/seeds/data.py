"""Статические пулы данных сидов (PRD §10): ФИО, стеки по
специализациям (взвешенные правдоподобные комбинации), шаблоны «о
себе», рыночные вилки 2026, θ-полосы грейдов (§6).

Всё константное — детерминизм датасета зависит только от rng и этих
таблиц, ни от сети, ни от времени.
"""

from ..constants import GRADES, SPECIALIZATION_TITLES, SPECIALIZATIONS

SPEC_TITLES = SPECIALIZATION_TITLES

# --- θ-полосы грейдов (§6): intern < −1 ≤ junior < 0.5 ≤ middle < 2 ≤ senior
# генерация — строго внутри полосы (сжатие к центру, чтобы θ не липла
# к границам)
GRADE_BANDS: dict[str, tuple[float, float]] = {
    "intern": (-2.5, -1.0),
    "junior": (-1.0, 0.5),
    "middle": (0.5, 2.0),
    "senior": (2.0, 3.5),
}

DEEP_SPECS = ("backend", "frontend", "qa")  # ≥ 10-12 кандидатов на грейд
WIDE_SPECS = tuple(s for s in SPECIALIZATIONS if s not in DEEP_SPECS)

DEEP_PER_GRADE = 12
WIDE_PER_GRADE = 9

FIRST_NAMES_M = [
    "Александр", "Алексей", "Андрей", "Артём", "Богдан", "Вадим",
    "Виктор", "Владимир", "Глеб", "Даниил", "Денис", "Дмитрий",
    "Евгений", "Егор", "Иван", "Илья", "Кирилл", "Максим",
    "Михаил", "Никита", "Олег", "Павел", "Роман", "Сергей",
    "Станислав", "Тимофей", "Фёдор", "Юрий",
]
FIRST_NAMES_F = [
    "Александра", "Алина", "Анастасия", "Анна", "Валерия", "Вера",
    "Виктория", "Галина", "Дарья", "Евгения", "Екатерина", "Елена",
    "Жанна", "Зоя", "Ирина", "Ксения", "Лариса", "Мария",
    "Надежда", "Наталья", "Ольга", "Полина", "Светлана", "Софья",
    "Татьяна", "Ульяна", "Юлия", "Яна",
]
LAST_NAMES_M = [
    "Алексеев", "Белов", "Васильев", "Волков", "Гусев", "Егоров",
    "Жуков", "Захаров", "Иванов", "Козлов", "Крылов", "Кузнецов",
    "Лебедев", "Морозов", "Николаев", "Новиков", "Орлов", "Павлов",
    "Петров", "Романов", "Семёнов", "Смирнов", "Соколов", "Тарасов",
    "Федоров", "Харитонов", "Чернов", "Шестаков",
]
LAST_NAMES_F = [
    "Алексеева", "Белова", "Васильева", "Волкова", "Гусева", "Егорова",
    "Жукова", "Захарова", "Иванова", "Козлова", "Крылова", "Кузнецова",
    "Лебедева", "Морозова", "Николаева", "Новикова", "Орлова", "Павлова",
    "Петрова", "Романова", "Семёнова", "Смирнова", "Соколова", "Тарасова",
    "Федорова", "Харитонова", "Чернова", "Шестакова",
]

# стеки: (технология, вес) — ядро специализации с большим весом,
# смежные технологии реже; выборка 3–6 уникальных
STACK_POOLS: dict[str, list[tuple[str, int]]] = {
    "backend": [
        ("python", 10), ("postgresql", 9), ("git", 8), ("fastapi", 7),
        ("redis", 7), ("docker", 7), ("linux", 6), ("sqlalchemy", 5),
        ("django", 4), ("go", 4), ("kubernetes", 4), ("kafka", 3),
        ("celery", 3), ("nginx", 3), ("mysql", 3), ("grpc", 2),
        ("rabbitmq", 2), ("flask", 2),
    ],
    "frontend": [
        ("typescript", 9), ("react", 9), ("html", 9), ("css", 9),
        ("javascript", 8), ("git", 8), ("nextjs", 5), ("tailwind", 5),
        ("vue", 4), ("vite", 4), ("redux", 4), ("nodejs", 4),
        ("webpack", 3), ("jest", 3), ("figma", 3), ("graphql", 2),
        ("storybook", 1),
    ],
    "qa": [
        ("pytest", 8), ("git", 8), ("python", 7), ("sql", 7),
        ("selenium", 6), ("postman", 6), ("jira", 6), ("playwright", 4),
        ("allure", 4), ("docker", 4), ("ci-cd", 4), ("linux", 4),
        ("java", 3), ("jmeter", 2), ("kotlin", 2), ("rest-assured", 2),
    ],
    "fullstack": [
        ("nodejs", 8), ("git", 8), ("typescript", 7), ("react", 7),
        ("postgresql", 7), ("docker", 7), ("python", 6), ("nextjs", 5),
        ("redis", 5), ("fastapi", 4), ("graphql", 3), ("jest", 3),
        ("mongodb", 3), ("kubernetes", 3), ("nginx", 3), ("prisma", 2),
    ],
    "mobile": [
        ("kotlin", 8), ("git", 8), ("swift", 7), ("android", 7),
        ("ios", 6), ("flutter", 5), ("dart", 5), ("coroutines", 4),
        ("compose", 4), ("firebase", 4), ("java", 4), ("gradle", 3),
        ("ci-cd", 3), ("sqlite", 3), ("rxjava", 2),
    ],
    "devops": [
        ("docker", 9), ("linux", 9), ("kubernetes", 8), ("git", 8),
        ("terraform", 7), ("bash", 7), ("gitlab-ci", 6), ("aws", 6),
        ("ansible", 5), ("prometheus", 5), ("grafana", 5),
        ("github-actions", 5), ("nginx", 5), ("helm", 4), ("python", 4),
        ("gcp", 3), ("azure", 3),
    ],
    "data-ml": [
        ("python", 10), ("pandas", 8), ("numpy", 8), ("sql", 7),
        ("git", 7), ("sklearn", 6), ("jupyter", 6), ("pytorch", 5),
        ("docker", 5), ("linux", 5), ("tensorflow", 4), ("mlflow", 3),
        ("airflow", 3), ("spark", 3), ("catboost", 3), ("huggingface", 3),
        ("keras", 2),
    ],
}

ABOUT_TEMPLATES = [
    "{title} с опытом {exp}. Основной стек: {stack}. Люблю чистый код "
    "и вдумчивое code review.",
    "Занимаюсь разработкой {exp}. Стек: {stack}. Интересуюсь "
    "архитектурой и производительностью.",
    "{title_cap}, стек — {stack}. Опыт {exp}. Люблю разбираться в "
    "чужом коде и доводить задачи до прода.",
    "Работаю {title_dat} {exp}. Стек: {stack}. Ценю понятные "
    "требования и честные вилки.",
    "{title_cap}. Пишу на {stack_main}, опыт {exp}. Участвую в "
    "пет-проектах и читаю профильные каналы.",
    "Опыт {exp}, стек: {stack}. Ищу команду, где важен инженерный "
    "процесс, а не только скорость.",
]

# рыночные вилки 2026, ₽/мес (from, to) — §10 «по рыночным
# распределениям на 2026», чтобы виджет §7.5.5 выглядел честно
MARKET_SALARY: dict[str, dict[str, tuple[int, int]]] = {
    "backend": {
        "intern": (80_000, 120_000), "junior": (120_000, 200_000),
        "middle": (250_000, 400_000), "senior": (400_000, 600_000),
    },
    "frontend": {
        "intern": (70_000, 110_000), "junior": (110_000, 180_000),
        "middle": (200_000, 350_000), "senior": (350_000, 550_000),
    },
    "qa": {
        "intern": (60_000, 100_000), "junior": (100_000, 160_000),
        "middle": (180_000, 300_000), "senior": (300_000, 450_000),
    },
    "fullstack": {
        "intern": (80_000, 120_000), "junior": (130_000, 200_000),
        "middle": (260_000, 400_000), "senior": (400_000, 620_000),
    },
    "mobile": {
        "intern": (80_000, 120_000), "junior": (130_000, 200_000),
        "middle": (250_000, 380_000), "senior": (380_000, 580_000),
    },
    "devops": {
        "intern": (90_000, 130_000), "junior": (140_000, 220_000),
        "middle": (280_000, 420_000), "senior": (420_000, 650_000),
    },
    "data-ml": {
        "intern": (90_000, 140_000), "junior": (150_000, 240_000),
        "middle": (300_000, 450_000), "senior": (450_000, 700_000),
    },
}

COMPANY_NAMES = [
    "Вектор Софт", "Норд Код", "Атлас Дев", "Квант Лабс", "Точка Зрения",
    "Северный Бит", "Меридиан Пайп", "Гиперион Тех", "Дельта Системы",
    "Октава ИТ", "Прагма Софт", "Рубеж Диджитал", "Сфера Клауд",
    "Тандем Код", "Формат Ноль",
]

COMPANY_INDUSTRIES = [
    "финтех", "ритейл-тех", "образовательные платформы", "логистика",
    "медтех", "геймдев", "телеком", "промышленная автоматизация",
]

# потребности: 3 на демо-работодателе + 3 на сид-компаниях (§10)
NEED_DEFS = [
    {
        "company": "demo",
        "raw_text": "Ищем backend-разработчика (Python, FastAPI) уровня "
        "middle в команду платёжного ядра. PostgreSQL, Redis, очереди. "
        "Полная занятость, гибрид.",
        "spec": "backend", "grade": "middle",
        "stack_must": ["python", "fastapi", "postgresql"],
        "stack_nice": ["redis", "kafka"],
    },
    {
        "company": "demo",
        "raw_text": "Нужен фронтендер middle на React + TypeScript для "
        "личного кабинета партнёра: дизайн-система, Next.js, работа с API.",
        "spec": "frontend", "grade": "middle",
        "stack_must": ["typescript", "react", "nextjs"],
        "stack_nice": ["tailwind", "redux"],
    },
    {
        "company": "demo",
        "raw_text": "Ищем QA-инженера junior с ростом в автоматизацию: "
        "ручное тестирование веба, pytest, SQL для проверок.",
        "spec": "qa", "grade": "junior",
        "stack_must": ["pytest", "sql"],
        "stack_nice": ["selenium", "postman"],
    },
    {
        "company": 1,  # Вектор Софт
        "raw_text": "Требуется senior DevOps: Kubernetes в проде, "
        "Terraform, наблюдаемость (Prometheus/Grafana), on-call.",
        "spec": "devops", "grade": "senior",
        "stack_must": ["kubernetes", "terraform", "linux"],
        "stack_nice": ["prometheus", "aws"],
    },
    {
        "company": 2,  # Норд Код
        "raw_text": "ML-инженер middle: классический ML на табличных "
        "данных, sklearn/catboost, вывод моделей в прод (Docker, FastAPI).",
        "spec": "data-ml", "grade": "middle",
        "stack_must": ["python", "sklearn", "sql"],
        "stack_nice": ["catboost", "docker"],
    },
    {
        "company": 3,  # Атлас Дев
        "raw_text": "Ищем senior backend (Go или Python) на высоконагруженный "
        "API-шлюз: gRPC, Kubernetes, оптимизация под нагрузкой.",
        "spec": "backend", "grade": "senior",
        "stack_must": ["go", "kubernetes", "postgresql"],
        "stack_nice": ["grpc", "redis"],
    },
]

INVITATION_TEXTS = [
    "Добрый день! Посмотрели ваш профиль — очень подходите под нашу "
    "команду {spec}. Готовы обсудить детали позиции.",
    "Здравствуйте! У нас открыта позиция {spec} — стек и грейд совпали "
    "почти идеально. Расскажем подробнее на созвоне.",
    "Добрый день! Ваш подтверждённый грейд и достижения впечатлили. "
    "Приглашаем на позицию {spec} в продуктовую команду.",
    "Здравствуйте! Ищем как раз такого специалиста ({spec}). Вилка "
    "честная, команда сильная — откликнитесь, если интересно.",
]

CONTACT_METHODS = ["telegram", "email", "телефон"]

__all__ = [
    "GRADES", "GRADE_BANDS", "DEEP_SPECS", "WIDE_SPECS",
    "DEEP_PER_GRADE", "WIDE_PER_GRADE",
    "FIRST_NAMES_M", "FIRST_NAMES_F", "LAST_NAMES_M", "LAST_NAMES_F",
    "STACK_POOLS", "SPEC_TITLES", "ABOUT_TEMPLATES", "MARKET_SALARY",
    "COMPANY_NAMES", "COMPANY_INDUSTRIES", "NEED_DEFS",
    "INVITATION_TEXTS", "CONTACT_METHODS",
]
