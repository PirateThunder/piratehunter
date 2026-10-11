"""Справочные константы домена (PRD §6).

Полный справочник специализаций/грейдов/тем живёт в core (catalog),
backend тянет его по HTTP и кэширует (GET /api/v1/catalog). Здесь —
только то, что нужно самому backend: порядок грейдов для кулдаунов
и валидация grade_target.
"""

# грейды — уровни навыков, подтверждаемые тестом (не стаж), PRD §6
GRADES = ("intern", "junior", "middle", "senior")

# «ниже/выше» по шкале грейдов (кулдауны §7.4.3)
def grade_rank(grade: str) -> int:
    return GRADES.index(grade)


# специализации MVP (справочно; валидация — по каталогу core на фронте)
SPECIALIZATIONS = (
    "backend",
    "frontend",
    "fullstack",
    "mobile",
    "qa",
    "devops",
    "data-ml",
)

# человекочитаемые названия специализаций (карточки, PDF-профиль)
SPECIALIZATION_TITLES = {
    "backend": "бэкенд-разработчик",
    "frontend": "фронтенд-разработчик",
    "fullstack": "фулстек-разработчик",
    "mobile": "мобильный разработчик",
    "qa": "QA-инженер",
    "devops": "DevOps-инженер",
    "data-ml": "ML-инженер",
}

# тип ЗП-вилки (Q&A 06.10: гросс/нетто непринципиально, лишь бы явно)
SALARY_TYPES = ("gross", "net")
