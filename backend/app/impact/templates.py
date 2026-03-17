from __future__ import annotations

T_HEADLINE_RATIO = "HEADLINE_RATIO"
T_HEADLINE_PERCENTILE = "HEADLINE_PERCENTILE"
T_HEADLINE_FALLBACK = "HEADLINE_FALLBACK"
T_EXEC_SUMMARY = "EXEC_SUMMARY"
T_EXEC_SUMMARY_LOW_DATA = "EXEC_SUMMARY_LOW_DATA"
T_QUOTE_PERCENTILE = "QUOTE_PERCENTILE"
T_QUOTE_RATIO = "QUOTE_RATIO"
T_POL_NOTE = "POL_NOTE"

_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        T_HEADLINE_RATIO: "{case_type_title} case pending {duration_years:.1f} years, {ratio:.1f}x longer than similar cases.",
        T_HEADLINE_PERCENTILE: "{case_type_title} case is slower than {percentile:.0f}% of comparable cases.",
        T_HEADLINE_FALLBACK: "Case timeline indicates prolonged proceedings relative to available records.",
        T_EXEC_SUMMARY: "This {case_type} case has {status_phrase} for {duration_human}. Compared with similar cases, it appears unusually slow based on court-level analytics and benchmark data.",
        T_EXEC_SUMMARY_LOW_DATA: "This case has {status_phrase} for {duration_human}. Comparable-case data is limited, so the assessment should be treated as preliminary.",
        T_QUOTE_PERCENTILE: "This case is slower than {percentile:.0f}% of comparable cases.",
        T_QUOTE_RATIO: "This case has taken about {ratio:.1f}x longer than similar cases.",
        T_POL_NOTE: "The observed delay pattern suggests value in reviewing listing efficiency and case-flow transparency at this court level.",
    },
    "hi": {},
}


def get_template(key: str, locale: str = "en") -> str:
    lang = locale if locale in _TEMPLATES else "en"
    if key in _TEMPLATES.get(lang, {}):
        return _TEMPLATES[lang][key]
    return _TEMPLATES["en"][key]
