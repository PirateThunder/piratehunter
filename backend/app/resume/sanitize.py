"""Обезличивание текста резюме перед отправкой в LLM-контур (PRD
§3.4: «резюме перед разбором обезличивается — вырезаем ФИО/контакты»;
ПДн в LLM не уходят ни при каком провайдере).

Вырезаем машинно-распознаваемые контакты: email, телефоны, telegram-
хендлы, URL. ФИО regex'ом достоверно не вырезать — его не должно быть
в контракте core (парсер возвращает только spec/стек/стаж), а сам
текст уходит в internal core, не наружу (§4.2).
"""

import re

# порядок важен: URL раньше email (mailto:/ссылки с @), email раньше
# telegram-хендлов
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)
TG_RE = re.compile(r"(?<![\w.+-])@[\w_]{3,32}")

REPLACEMENTS = (
    (URL_RE, "[ссылка]"),
    (EMAIL_RE, "[email]"),
    (PHONE_RE, "[телефон]"),
    (TG_RE, "[контакт]"),
)


def sanitize_resume_text(text: str) -> str:
    """Текст резюме без контактов — то, что уйдёт в core/LLM."""
    for pattern, replacement in REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text
