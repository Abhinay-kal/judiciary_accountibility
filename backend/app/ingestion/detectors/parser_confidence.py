"""Parser-confidence scoring for ingestion runs.

Produces a single float ``[0.0, 1.0]`` that represents how well the
current run's parser performed across all extracted records.

Scoring components (equal weight by default)
---------------------------------------------
1. **Field-presence rate** — fraction of required fields that exist in
   at least one record.
2. **Completeness rate** — across all records, fraction of
   required-field slots that are non-null.
3. **Non-error rate** — fraction of records that were parsed without
   raising any exception (``parse_errors / total``).
4. **Type-validity rate** — fraction of field values whose Python type
   matches the expected type declared in *field_types*.

Any component for which there is no data defaults to ``1.0`` (benefit
of the doubt).

Usage::

    from app.ingestion.detectors.parser_confidence import ParserConfidenceScorer

    scorer = ParserConfidenceScorer(
        required_fields=["case_id", "court_name", "filing_date"],
        field_types={"case_id": str, "filing_date": str},
    )
    score = scorer.score(records, parse_error_count=2)
"""
from __future__ import annotations

from typing import Any, Optional, Sequence, Type


class ParserConfidenceScorer:
    """Stateless, pure scorer — create once, reuse across runs."""

    def __init__(
        self,
        required_fields: Sequence[str] = (),
        field_types: Optional[dict[str, Type]] = None,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Parameters
        ----------
        required_fields:
            Fields that *must* be present in a valid record.
        field_types:
            Mapping of field name → expected Python type.
            Only fields listed here are type-checked.
        weights:
            Override component weights.  Keys: ``presence``,
            ``completeness``, ``no_errors``, ``type_validity``.
            Must sum to 1.0.
        """
        self._required = list(required_fields)
        self._field_types: dict[str, Type] = field_types or {}
        default_weights = {
            "presence": 0.25,
            "completeness": 0.35,
            "no_errors": 0.25,
            "type_validity": 0.15,
        }
        if weights:
            default_weights.update(weights)
        self._weights = default_weights

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        records: Sequence[dict[str, Any]],
        parse_error_count: int = 0,
        total_attempted: Optional[int] = None,
    ) -> float:
        """Compute the confidence score for a batch of parsed records.

        Parameters
        ----------
        records:
            Successfully parsed records.
        parse_error_count:
            Number of records that raised a parse exception and were
            discarded.
        total_attempted:
            Total records attempted (defaults to
            ``len(records) + parse_error_count``).

        Returns
        -------
        float
            Score in [0.0, 1.0].
        """
        total = total_attempted if total_attempted is not None else (
            len(records) + parse_error_count
        )
        w = self._weights

        presence_score = self._field_presence_score(records)
        completeness_score = self._completeness_score(records)
        no_error_score = self._no_error_score(parse_error_count, total)
        type_score = self._type_validity_score(records)

        composite = (
            w["presence"] * presence_score
            + w["completeness"] * completeness_score
            + w["no_errors"] * no_error_score
            + w["type_validity"] * type_score
        )
        return round(max(0.0, min(1.0, composite)), 4)

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def _field_presence_score(self, records: Sequence[dict]) -> float:
        """Fraction of required fields seen in at least one record."""
        if not self._required or not records:
            return 1.0
        seen = set()
        for rec in records:
            seen.update(rec.keys())
        present = sum(1 for f in self._required if f in seen)
        return present / len(self._required)

    def _completeness_score(self, records: Sequence[dict]) -> float:
        """Across all <record, required_field> pairs, fraction non-null."""
        if not self._required or not records:
            return 1.0
        total_slots = len(records) * len(self._required)
        filled = sum(
            1
            for rec in records
            for field in self._required
            if rec.get(field) is not None
        )
        return filled / total_slots

    @staticmethod
    def _no_error_score(parse_error_count: int, total: int) -> float:
        """``1 - (errors / total)``."""
        if total <= 0:
            return 1.0
        return max(0.0, 1.0 - (parse_error_count / total))

    def _type_validity_score(self, records: Sequence[dict]) -> float:
        """Fraction of typed-field values with correct Python type."""
        if not self._field_types or not records:
            return 1.0
        total_checks = 0
        valid_checks = 0
        for rec in records:
            for field, expected_type in self._field_types.items():
                value = rec.get(field)
                if value is not None:
                    total_checks += 1
                    if isinstance(value, expected_type):
                        valid_checks += 1
        if total_checks == 0:
            return 1.0
        return valid_checks / total_checks
