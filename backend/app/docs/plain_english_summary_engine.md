# Plain-English Summary Engine

## Purpose
Converts case analytics into deterministic, evidence-based explanations that non-technical users can understand.

## Design principles
- deterministic and template-driven generation
- non-accusatory, defamation-safe wording
- confidence-aware qualifiers
- localization-ready templates
- consistent structured output for UI and APIs

## Package structure
- app/explanations/templates.py
- app/explanations/generator.py
- app/explanations/context.py
- app/explanations/confidence.py
- app/explanations/localization.py
- app/explanations/formatter.py

## Input metrics used
- normalized_delay
- delay percentile ranking
- survival probability
- strategic_delay_score
- importance_score
- baseline comparisons
- anomaly flags
- confidence metrics

## Output structure
The engine returns:
- short_summary
- detailed_summary
- bullet_points[]
- confidence_note
- key_metrics_used[]
- summary_confidence

## Case table integration
Added columns:
- plain_summary_short
- plain_summary_detailed
- summary_confidence
- last_summary_update

Migration:
- alembic/versions/0014_plain_english_summary_fields.py

## API integration
Case endpoints now include:
- plain_summary_short
- plain_summary_detailed
- summary_confidence
- last_summary_update
- plain_summary (full structured object)

## Batch/precompute integration
Summaries are precomputed and persisted when analytics are refreshed in:
- tasks/importance_recompute.py
- tasks/delay_analytics.py

## Language safety
The engine avoids blame assignment and uses pattern-oriented statements:
- "The case shows an unusually long duration"
- not actor-attribution statements.

## Fallback behavior
If comparable data is missing, output:
- "Not enough comparable cases are currently available to assess delay reliably."

## Future localization
Localization is key-based and supports fallback routing. `hi` currently uses English templates as placeholders for deterministic rollout.
