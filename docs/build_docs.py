#!/usr/bin/env python3
# Сборка единого PDF/HTML технической документации PirateHunter.
# Источники: README.md + docs/*.md (ARCHITECTURE, RUN, TESTING, VALIDATION,
# MATCHING, FSP-INTEGRATION, API). md → styled HTML → soffice → PDF.
# Запуск из корня репо: python3 docs/build_docs.py
import html
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
SOURCES = [
    ("README.md", None),
    ("docs/ARCHITECTURE.md", "1. Архитектура"),
    ("docs/RUN.md", "2. Запуск и развёртывание"),
    ("docs/TESTING.md", "3. Тестирование"),
    ("docs/VALIDATION.md", "4. Валидация"),
    ("docs/MATCHING.md", "5. Механика подбора"),
    ("docs/FSP-INTEGRATION.md", "6. Интеграция с ФСП"),
    ("docs/API.md", "7. API"),
]


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)`([^`]+?)`(?!\w)", r'<code class="mono">\1</code>', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def md_to_html(md: str) -> str:
    """Минимальный md→html: заголовки, таблицы, списки, код, параграфы."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # закрывающий ```
            out.append("<pre>" + html.escape("\n".join(buf)) + "</pre>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1)) + 1  # h1 источника -> h2 сборки
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and "---" in lines[i + 1]:
            header = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                m2 = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", lines[i])
                if not m2 or m2.group(2)[0].isdigit() != ordered:
                    break
                items.append(f"<li>{inline(m2.group(3))}</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if line.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        out.append(f"<p>{inline(line)}</p>")
        i += 1
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Inter', 'Liberation Sans', sans-serif; color: #1B1C21;
       font-size: 10pt; line-height: 1.45; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 16pt 0 6pt; color: #1B1C21;
     border-bottom: 2px solid #402FFF; padding-bottom: 3pt; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 11pt 0 4pt; color: #2D2E37; page-break-after: avoid; }
h4 { font-size: 10.5pt; margin: 9pt 0 3pt; color: #2D2E37; }
p { margin: 4pt 0; }
ul, ol { margin: 4pt 0 4pt 18pt; padding: 0; }
li { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 8.4pt; }
th { background: #1B1C21; color: #fff; text-align: left; padding: 4pt 6pt; }
td { border-bottom: 1px solid #E4E4E8; padding: 3.5pt 6pt; vertical-align: top; }
tr { page-break-inside: avoid; }
.mono, code { font-family: 'JetBrains Mono', 'Liberation Mono', monospace;
              font-size: 8.4pt; }
code { background: #EDEDED; padding: 0 3pt; border-radius: 3pt; }
pre { background: #1B1C21; color: #EDEDED; padding: 8pt 10pt; border-radius: 6pt;
      font-size: 7.6pt; line-height: 1.4; white-space: pre-wrap;
      font-family: 'JetBrains Mono', monospace; }
a { color: #402FFF; text-decoration: none; }
hr { border: none; border-top: 1px solid #EDEDED; margin: 8pt 0; }
.cover { padding-top: 180pt; }
.cover .brand { color: #402FFF; font-size: 13pt; letter-spacing: 2pt;
                text-transform: uppercase; margin-bottom: 8pt; font-weight: 700; }
.cover .sub { font-size: 12.5pt; color: #838388; margin-top: 4pt; }
.cover .meta { margin-top: 110pt; color: #4d5560; font-size: 10pt; }
.cover .meta b { color: #1B1C21; }
.pagebreak { page-break-before: always; }
.section { page-break-before: always; }
"""


def main() -> None:
    parts = [
        "<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
        "<title>PirateHunter — документация</title>"
        f"<style>{CSS}</style></head><body>",
        '<div class="cover">'
        '<div class="brand">PirateHunter · трек ФСП · ЛЦТ 2026</div>'
        "<h1>Техническая документация</h1>"
        '<div class="sub">Платформа-агрегатор ИТ-вакансий с обратной механикой:<br>'
        "работодатель сам находит кандидата в категоризованной базе "
        "(специализация × подтверждённый тестом грейд)</div>"
        '<div class="meta">'
        "<p><b>Живой сервис:</b> https://piratehunter.fun</p>"
        "<p><b>OpenAPI:</b> /docs на backend (BACK_ENV=local)</p>"
        "<p><b>Репозиторий:</b> публичный GitHub (см. README)</p>"
        "<p><b>Дата сборки:</b> 11 октября 2026</p>"
        "</div></div>",
    ]
    for rel, title in SOURCES:
        body = (ROOT / rel).read_text(encoding="utf-8")
        block = md_to_html(body)
        if title:
            block = f'<div class="section"><h1>{html.escape(title)}</h1>{block}</div>'
        else:
            block = f'<div class="section">{block}</div>'
        parts.append(block)
    parts.append("</body></html>")

    out_html = OUT / "piratehunter-docs.html"
    out_html.write_text("\n".join(parts), encoding="utf-8")
    print(f"html ok: {out_html}")

    soffice = shutil.which("soffice")
    if not soffice:
        print("soffice не найден — PDF не собран (html готов)")
        return
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(OUT),
         str(out_html)],
        check=True, capture_output=True, timeout=180,
    )
    pdf = out_html.with_suffix(".pdf")
    print(f"pdf ok: {pdf} ({pdf.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
