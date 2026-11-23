"""Второй язык интерфейса, графиков и отчётов.

Язык запроса хранится в contextvar: его выставляет middleware в app/main.py
(?lang=en|ru → cookie `lang` → Accept-Language → ru). Всё, что строится внутри
запроса (страницы, графики, DOCX/PDF/PPTX, ответы чата), берёт язык оттуда.

Русские строки в коде обёрнуты в tr("...") и служат ключами словаря
app/core/i18n_en.json. Нет перевода — показывается русский текст.
Шаблоны с позиционными полями: tr("Готово: {0}", value).
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path

LANGS = ("ru", "en")
DEFAULT_LANG = "ru"
_current: ContextVar[str] = ContextVar("lang", default=DEFAULT_LANG)

_EN: dict[str, str] = json.loads((Path(__file__).with_name("i18n_en.json")).read_text(encoding="utf-8"))


def get_lang() -> str:
    return _current.get()


def set_lang(lang: str):
    return _current.set(lang if lang in LANGS else DEFAULT_LANG)


def reset_lang(token) -> None:
    _current.reset(token)


def lang_from_accept_language(header: str | None) -> str:
    if not header:
        return DEFAULT_LANG
    first = header.split(",")[0].strip().lower()
    return "ru" if first.startswith(("ru", "uk", "be", "kk")) else "en"


def tr(text: str, *args) -> str:
    template = _EN.get(text, text) if _current.get() == "en" else text
    return template.format(*args) if args else template


def install_jinja(env) -> None:
    """tr() и current_lang() в шаблонах; язык берется на момент рендера."""
    env.globals["tr"] = tr
    env.globals["current_lang"] = get_lang
