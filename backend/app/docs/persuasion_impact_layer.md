# Persuasion and Impact Layer

## Purpose
The impact layer translates verified delay analytics into credible, audience-ready narratives. It is deterministic, template-driven, and designed to remain defamation-safe.

## Package
- `app/impact/templates.py`: locale-ready template registry.
- `app/impact/narratives.py`: orchestrator that returns structured impact content.
- `app/impact/audience.py`: audience adaptation for journalists, policymakers, legal professionals, civil society, and general public.
- `app/impact/highlights.py`: headline, takeaways, and quote builders.
- `app/impact/framing.py`: "why it matters" and impact consequence framing.
- `app/impact/calls_to_action.py`: neutral, lawful action suggestions.
- `app/impact/comparators.py`: relative metrics and benchmark comparators.
- `app/impact/credibility.py`: confidence, source, method, and uncertainty notes.

## Output Contract
`generate_case_impact(...)` returns:
- `headline`
- `executive_summary`
- `key_takeaways[]`
- `why_it_matters`
- `impact_statement`
- `calls_to_action[]`
- `journalist_quote`
- `policymaker_note`
- `credibility_notes`
- `impact_confidence`

## Defamation-Safety Guardrails
- No allegation of intent, guilt, or conspiracy.
- No naming of motives.
- Pattern and metric language only.
- Uncertainty note included when comparator data is thin.

## Storage
Persisted on `cases`:
- `impact_headline`
- `impact_summary`
- `impact_confidence`
- `impact_last_updated`

## Triggering and Caching
Impact content is generated:
- during delay analytics refresh,
- during importance recomputation,
- via manual API trigger `POST /cases/{id}/impact/regenerate`.

Case-list and case-detail cache namespaces are invalidated after manual regeneration.

## UI Pattern
Case detail page renders:
- headline highlight card,
- quote block,
- summary and key-takeaway panels,
- suggested actions,
- downloadable investigation brief link.

## Localization
Template selection is locale-key based. English templates are default. Additional locales can be added without modifying narrative logic.
