from __future__ import annotations

from app.explanations.templates import DEFAULT_TEMPLATES_EN

SUPPORTED_LOCALES = {"en", "hi"}

# Hindi placeholders intentionally mirror English keys to keep localization deterministic.
_LOCALE_MAP: dict[str, dict[str, str]] = {
    "en": DEFAULT_TEMPLATES_EN,
    "hi": DEFAULT_TEMPLATES_EN,
}


def get_template(key: str, locale: str = "en") -> str:
    lang = locale if locale in SUPPORTED_LOCALES else "en"
    template = _LOCALE_MAP.get(lang, {}).get(key)
    if template:
        return template
    return DEFAULT_TEMPLATES_EN[key]
