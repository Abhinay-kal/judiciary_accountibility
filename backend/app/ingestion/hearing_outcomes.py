from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, Iterable, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.metrics import record_hearing_outcome_metrics
from app.models import Hearing, HearingOutcomeAudit, HearingOutcomeType, Order
from app.ml.config import get_ml_settings

_WORD_RE = re.compile(r"[a-z][a-z.]*")
_SPACE_RE = re.compile(r"\s+")
_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
_PUNCT_RE = re.compile(r"[^a-z0-9.\s]+")

_LISTING_HINTS = (
    "for orders",
    "for hearing",
    "for admission",
    "item no",
    "court no",
    "serial no",
    "listed on",
)

_DISPOSAL_TOKENS = (
    "disposed",
    "dismissed",
    "pronounced",
    "judgment",
    "allowed",
    "dismissed with costs",
    "ug",
)


@dataclass(frozen=True)
class RuleSpec:
    name: str
    outcome_type: HearingOutcomeType
    confidence: float
    keywords: tuple[str, ...]


@dataclass
class CorroboratingSignal:
    outcome_type: HearingOutcomeType
    confidence: float
    source_name: str
    evidence_id: str | None = None
    matched_keywords: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    outcome_type: HearingOutcomeType
    confidence: float
    matched_rules: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)
    parser_version: str = "outcome-rules-v1"
    explanation: str | None = None
    ml_applied: bool = False
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_type": self.outcome_type.value,
            "confidence": round(self.confidence, 4),
            "matched_rules": self.matched_rules,
            "matched_keywords": self.matched_keywords,
            "evidence_ids": self.evidence_ids,
            "source_names": self.source_names,
            "parser_version": self.parser_version,
            "explanation": self.explanation,
            "ml_applied": self.ml_applied,
            "needs_review": self.needs_review,
        }


@lru_cache(maxsize=1)
def _rule_specs() -> tuple[RuleSpec, ...]:
    return (
        RuleSpec(
            name="adjourned_keywords",
            outcome_type=HearingOutcomeType.ADJOURNED,
            confidence=0.95,
            keywords=(
                "adjourn",
                "postponed",
                "deferred",
                "put up",
                "relisted",
                "adjd",
                "adjd.",
                "adj.",
                "adjourned to",
            ),
        ),
        RuleSpec(
            name="heard_keywords",
            outcome_type=HearingOutcomeType.HEARD,
            confidence=0.92,
            keywords=(
                "heard",
                "argument heard",
                "taken up",
                "considered",
                "heard today",
            ),
        ),
        RuleSpec(
            name="order_reserved_keywords",
            outcome_type=HearingOutcomeType.ORDER_RESERVED,
            confidence=0.93,
            keywords=(
                "order reserved",
                "order kept",
                "reserved",
                "orders reserved",
            ),
        ),
        RuleSpec(
            name="disposed_keywords",
            outcome_type=HearingOutcomeType.DISPOSED,
            confidence=0.96,
            keywords=_DISPOSAL_TOKENS,
        ),
        RuleSpec(
            name="not_reached_keywords",
            outcome_type=HearingOutcomeType.NOT_REACHED,
            confidence=0.90,
            keywords=(
                "not reached",
                "not taken up",
                "not heard",
                "case not taken",
            ),
        ),
        RuleSpec(
            name="no_proceedings_keywords",
            outcome_type=HearingOutcomeType.NO_PROCEEDINGS,
            confidence=0.90,
            keywords=("no proceedings",),
        ),
    )


@lru_cache(maxsize=1)
def _compiled_keyword_patterns() -> dict[str, dict[str, re.Pattern[str]]]:
    compiled: dict[str, dict[str, re.Pattern[str]]] = {}
    for rule in _rule_specs():
        compiled[rule.name] = {}
        for keyword in rule.keywords:
            parts = [re.escape(part) for part in keyword.casefold().split() if part]
            if not parts:
                continue
            pattern = r"\b" + r"\s+".join(parts) + r"\b"
            compiled[rule.name][keyword] = re.compile(pattern)
    return compiled


def _normalize_text(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    lowered = raw_text.casefold()
    lowered = _PUNCT_RE.sub(" ", lowered)
    lowered = _SPACE_RE.sub(" ", lowered).strip()
    return lowered


def _contains_keyword(text: str, keyword: str) -> bool:
    parts = [re.escape(part) for part in keyword.casefold().split() if part]
    if not parts:
        return False
    pattern = r"\b" + r"\s+".join(parts) + r"\b"
    return re.search(pattern, text) is not None


def _match_rule(text: str, rule: RuleSpec) -> list[str]:
    patterns = _compiled_keyword_patterns().get(rule.name, {})
    matched = [keyword for keyword, pattern in patterns.items() if pattern.search(text)]
    if rule.outcome_type != HearingOutcomeType.HEARD:
        return matched

    filtered: list[str] = []
    for keyword in matched:
        if keyword in {"heard", "heard today", "argument heard"} and re.search(r"\bnot\s+heard\b", text):
            continue
        if keyword == "taken up" and re.search(r"\bnot\s+taken\s+up\b", text):
            continue
        filtered.append(keyword)
    return filtered


def _is_listing_only(text: str, listing_type: str | None, source_name: str | None) -> bool:
    if any(_contains_keyword(text, token) for token in _LISTING_HINTS):
        return True
    return (not text and bool(listing_type)) or (not text and source_name in {"high_court", "supreme_court", "ecourts"})


def _combine_confidences(confidences: Sequence[float]) -> float:
    if not confidences:
        return 0.0
    remaining = 1.0
    for confidence in confidences:
        remaining *= 1.0 - max(0.0, min(confidence, 1.0))
    return max(0.0, min(1.0, 1.0 - remaining))


def _should_use_ml(result: ParseResult) -> bool:
    return result.outcome_type == HearingOutcomeType.OTHER or result.confidence < 0.75


def parse_outcome_text(
    raw_text: str | None,
    *,
    listing_type: str | None = None,
    source_name: str | None = None,
    parser_version: str | None = None,
    has_order_pdf: bool = False,
    corroborating_signals: Sequence[CorroboratingSignal] | None = None,
    allow_ml: bool = True,
) -> ParseResult:
    settings = get_settings()
    parser_version = parser_version or settings.outcome_parser_version
    normalized = _normalize_text(raw_text)
    source_names = [source_name] if source_name else []
    non_ascii = bool(raw_text and _NON_ASCII_RE.search(raw_text))
    english_tokens = _WORD_RE.findall(normalized)

    if non_ascii and not english_tokens:
        result = ParseResult(
            outcome_type=HearingOutcomeType.OTHER,
            confidence=0.30,
            matched_rules=["non_english_review"],
            source_names=source_names,
            parser_version=parser_version,
            explanation="Non-English or unsupported script outcome text; queued for review.",
        )
        return _finalize_result(result, corroborating_signals or [], has_order_pdf=has_order_pdf, allow_ml=False, raw_text=raw_text)

    for rule in _rule_specs():
        keywords = _match_rule(normalized, rule)
        if keywords:
            result = ParseResult(
                outcome_type=rule.outcome_type,
                confidence=rule.confidence,
                matched_rules=[rule.name],
                matched_keywords=keywords,
                source_names=source_names,
                parser_version=parser_version,
                explanation=f"Matched {rule.name}.",
            )
            return _finalize_result(result, corroborating_signals or [], has_order_pdf=has_order_pdf, allow_ml=allow_ml, raw_text=raw_text)

    if _is_listing_only(normalized, listing_type, source_name):
        result = ParseResult(
            outcome_type=HearingOutcomeType.LISTED,
            confidence=0.85,
            matched_rules=["listing_only"],
            source_names=source_names,
            parser_version=parser_version,
            explanation="No outcome token found; treated as listing-only entry.",
        )
        return _finalize_result(result, corroborating_signals or [], has_order_pdf=has_order_pdf, allow_ml=allow_ml, raw_text=raw_text)

    result = ParseResult(
        outcome_type=HearingOutcomeType.OTHER,
        confidence=0.35,
        matched_rules=["ambiguous_text"],
        source_names=source_names,
        parser_version=parser_version,
        explanation="Ambiguous outcome text; human verification recommended.",
    )
    return _finalize_result(result, corroborating_signals or [], has_order_pdf=has_order_pdf, allow_ml=allow_ml, raw_text=raw_text)


def _finalize_result(
    result: ParseResult,
    corroborating_signals: Sequence[CorroboratingSignal],
    *,
    has_order_pdf: bool,
    allow_ml: bool,
    raw_text: str | None,
) -> ParseResult:
    result = _apply_corroboration(result, corroborating_signals, has_order_pdf=has_order_pdf)
    if allow_ml and _should_use_ml(result):
        ml_result = _apply_ml_fallback(result, raw_text=raw_text, has_order_pdf=has_order_pdf)
        if ml_result is not None:
            result = ml_result
    result.needs_review = result.outcome_type == HearingOutcomeType.OTHER or result.confidence < get_settings().default_outcome_confidence_verify
    return result


def _apply_corroboration(
    result: ParseResult,
    corroborating_signals: Sequence[CorroboratingSignal],
    *,
    has_order_pdf: bool,
) -> ParseResult:
    if not corroborating_signals:
        return result

    agreeing = [signal for signal in corroborating_signals if signal.outcome_type == result.outcome_type]
    order_disposal = [signal for signal in corroborating_signals if signal.outcome_type == HearingOutcomeType.DISPOSED]
    order_heard = [signal for signal in corroborating_signals if signal.outcome_type == HearingOutcomeType.HEARD]

    if has_order_pdf and order_disposal:
        strongest = max(order_disposal, key=lambda signal: signal.confidence)
        return ParseResult(
            outcome_type=HearingOutcomeType.DISPOSED,
            confidence=max(0.99, strongest.confidence),
            matched_rules=result.matched_rules + ["order_pdf_override"],
            matched_keywords=result.matched_keywords + strongest.matched_keywords,
            evidence_ids=result.evidence_ids + [signal.evidence_id for signal in order_disposal if signal.evidence_id],
            source_names=result.source_names + [signal.source_name for signal in order_disposal],
            parser_version=result.parser_version,
            explanation="Order PDF corroborated disposal on the same hearing date.",
        )

    if result.outcome_type == HearingOutcomeType.LISTED and order_heard:
        strongest = max(order_heard, key=lambda signal: signal.confidence)
        return ParseResult(
            outcome_type=strongest.outcome_type,
            confidence=max(0.88, strongest.confidence),
            matched_rules=result.matched_rules + ["same_date_order_override"],
            matched_keywords=result.matched_keywords + strongest.matched_keywords,
            evidence_ids=result.evidence_ids + [signal.evidence_id for signal in order_heard if signal.evidence_id],
            source_names=result.source_names + [signal.source_name for signal in order_heard],
            parser_version=result.parser_version,
            explanation="Cause list said listed, but a same-day order indicates proceedings occurred.",
        )

    if agreeing:
        boosted = _combine_confidences([result.confidence, *[signal.confidence for signal in agreeing]])
        result.confidence = max(result.confidence, boosted)
        result.matched_rules.append("multi_source_corroboration")
        result.matched_keywords.extend(
            keyword
            for signal in agreeing
            for keyword in signal.matched_keywords
            if keyword not in result.matched_keywords
        )
        result.evidence_ids.extend(signal.evidence_id for signal in agreeing if signal.evidence_id)
        result.source_names.extend(signal.source_name for signal in agreeing if signal.source_name not in result.source_names)
        result.explanation = "Independent sources corroborated the hearing outcome."
    return result


def _apply_ml_fallback(
    result: ParseResult,
    *,
    raw_text: str | None,
    has_order_pdf: bool,
) -> ParseResult | None:
    ml_settings = get_ml_settings()
    if not ml_settings.ml_parser_enabled:
        return None

    from app.ml.hearing_outcomes import OutcomeMLParser

    predictor = OutcomeMLParser()
    prediction = predictor.predict(
        raw_outcome_text=raw_text or "",
        source_type=(result.source_names[0] if result.source_names else "unknown"),
        parser_version=result.parser_version,
        presence_of_order_pdf=has_order_pdf,
    )


def coerce_corroborating_signal(payload: Any) -> CorroboratingSignal | None:
    if isinstance(payload, CorroboratingSignal):
        return payload
    if not isinstance(payload, dict):
        return None
    raw_outcome = payload.get("outcome_type")
    if raw_outcome is None:
        return None
    try:
        outcome_type = HearingOutcomeType(str(raw_outcome).upper())
    except ValueError:
        return None
    confidence = payload.get("confidence", 0.0)
    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0
    confidence_val = max(0.0, min(1.0, confidence_val))
    source_name = str(payload.get("source_name") or payload.get("source") or "unknown")
    evidence_id = payload.get("evidence_id")
    if evidence_id is not None:
        evidence_id = str(evidence_id)
    matched_keywords = [str(item) for item in (payload.get("matched_keywords") or []) if str(item).strip()]
    matched_rules = [str(item) for item in (payload.get("matched_rules") or []) if str(item).strip()]
    return CorroboratingSignal(
        outcome_type=outcome_type,
        confidence=confidence_val,
        source_name=source_name,
        evidence_id=evidence_id,
        matched_keywords=matched_keywords,
        matched_rules=matched_rules,
    )


def coerce_corroborating_signals(payloads: Iterable[Any] | None) -> list[CorroboratingSignal]:
    if not payloads:
        return []
    normalized: list[CorroboratingSignal] = []
    for payload in payloads:
        signal = coerce_corroborating_signal(payload)
        if signal is not None:
            normalized.append(signal)
    return normalized
    if prediction is None or prediction.confidence <= result.confidence:
        return None

    return ParseResult(
        outcome_type=prediction.outcome_type,
        confidence=prediction.confidence,
        matched_rules=result.matched_rules + ["ml_fallback"],
        matched_keywords=result.matched_keywords,
        evidence_ids=result.evidence_ids,
        source_names=result.source_names,
        parser_version=result.parser_version,
        explanation="ML fallback disambiguated a low-confidence rule-based classification.",
        ml_applied=True,
    )


def build_corroborating_signals(
    db: Session,
    *,
    case_id: int,
    hearing_date: date,
    current_source: str,
    existing_hearing: Hearing | None = None,
) -> list[CorroboratingSignal]:
    signals: list[CorroboratingSignal] = []

    orders = (
        db.query(Order)
        .filter(Order.case_id == case_id, Order.order_date == hearing_date, Order.is_deleted.is_(False))
        .all()
    )
    for order in orders:
        order_text = _normalize_text(order.raw_reference or order.order_link)
        if any(_contains_keyword(order_text, token) for token in _DISPOSAL_TOKENS):
            signals.append(
                CorroboratingSignal(
                    outcome_type=HearingOutcomeType.DISPOSED,
                    confidence=0.99,
                    source_name=order.source,
                    evidence_id=f"order:{order.id}",
                    matched_keywords=[token for token in _DISPOSAL_TOKENS if _contains_keyword(order_text, token)],
                    matched_rules=["order_pdf_disposal"],
                )
            )
        else:
            signals.append(
                CorroboratingSignal(
                    outcome_type=HearingOutcomeType.HEARD,
                    confidence=0.88,
                    source_name=order.source,
                    evidence_id=f"order:{order.id}",
                    matched_rules=["same_day_order_present"],
                )
            )

    if existing_hearing and existing_hearing.source and existing_hearing.source != current_source and existing_hearing.outcome_type:
        signals.append(
            CorroboratingSignal(
                outcome_type=existing_hearing.outcome_type,
                confidence=existing_hearing.outcome_confidence or 0.6,
                source_name=existing_hearing.source,
                evidence_id=f"hearing:{existing_hearing.id}",
                matched_rules=["existing_hearing_signal"],
            )
        )

    return signals


def apply_outcome_to_hearing(
    db: Session,
    hearing: Hearing,
    *,
    raw_outcome_text: str | None,
    listing_type: str | None,
    source_name: str,
    parser_version: str | None = None,
    additional_signals: Sequence[CorroboratingSignal] | None = None,
) -> ParseResult:
    parser_version = parser_version or get_settings().outcome_parser_version
    corroborating_signals = build_corroborating_signals(
        db,
        case_id=hearing.case_id,
        hearing_date=hearing.date,
        current_source=source_name,
        existing_hearing=hearing if hearing.id else None,
    )
    if additional_signals:
        corroborating_signals.extend(additional_signals)
    has_order_pdf = any(signal.evidence_id and signal.evidence_id.startswith("order:") for signal in corroborating_signals)
    result = parse_outcome_text(
        raw_outcome_text,
        listing_type=listing_type,
        source_name=source_name,
        parser_version=parser_version,
        has_order_pdf=has_order_pdf,
        corroborating_signals=corroborating_signals,
    )

    hearing.outcome_text = raw_outcome_text
    hearing.raw_outcome_text = raw_outcome_text
    hearing.outcome_type = result.outcome_type
    hearing.outcome_confidence = result.confidence
    hearing.parser_version = result.parser_version

    record_hearing_outcome_metrics(
        source_name=source_name,
        outcome_type=result.outcome_type.value,
        parser_version=result.parser_version,
        confidence=result.confidence,
        verify_threshold=get_settings().default_outcome_confidence_verify,
    )
    return result


def record_outcome_audit(
    db: Session,
    *,
    hearing: Hearing,
    action: str,
    explanation: str | None,
    admin_id: int | None,
    previous_outcome_type: HearingOutcomeType | None,
    previous_confidence: float | None,
    previous_parser_version: str | None,
) -> HearingOutcomeAudit:
    audit = HearingOutcomeAudit(
        hearing_id=hearing.id,
        admin_id=admin_id,
        action=action,
        explanation=explanation,
        previous_outcome_type=previous_outcome_type,
        new_outcome_type=hearing.outcome_type,
        previous_confidence=previous_confidence,
        new_confidence=hearing.outcome_confidence,
        previous_parser_version=previous_parser_version,
        new_parser_version=hearing.parser_version,
    )
    db.add(audit)
    db.flush()
    return audit


def annotate_hearing(
    db: Session,
    *,
    hearing: Hearing,
    outcome_type: HearingOutcomeType,
    explanation: str | None,
    admin_id: int,
) -> HearingOutcomeAudit:
    previous_outcome_type = hearing.outcome_type
    previous_confidence = hearing.outcome_confidence
    previous_parser_version = hearing.parser_version

    hearing.outcome_type = outcome_type
    hearing.outcome_confidence = 1.0
    hearing.annotated_by = admin_id
    hearing.annotated_at = datetime.now(timezone.utc)
    hearing.parser_version = f"{get_settings().outcome_parser_version}-manual"

    return record_outcome_audit(
        db,
        hearing=hearing,
        action="annotate",
        explanation=explanation,
        admin_id=admin_id,
        previous_outcome_type=previous_outcome_type,
        previous_confidence=previous_confidence,
        previous_parser_version=previous_parser_version,
    )


def reprocess_hearing(
    db: Session,
    *,
    hearing: Hearing,
    parser_version: str | None = None,
    admin_id: int | None = None,
    explanation: str | None = None,
) -> tuple[ParseResult, HearingOutcomeAudit]:
    previous_outcome_type = hearing.outcome_type
    previous_confidence = hearing.outcome_confidence
    previous_parser_version = hearing.parser_version
    result = apply_outcome_to_hearing(
        db,
        hearing,
        raw_outcome_text=hearing.raw_outcome_text or hearing.outcome_text,
        listing_type=hearing.listing_type,
        source_name=hearing.source,
        parser_version=parser_version,
    )
    audit = record_outcome_audit(
        db,
        hearing=hearing,
        action="reprocess",
        explanation=explanation,
        admin_id=admin_id,
        previous_outcome_type=previous_outcome_type,
        previous_confidence=previous_confidence,
        previous_parser_version=previous_parser_version,
    )
    return result, audit


def review_queue_query(db: Session, threshold: float):
    return (
        db.query(Hearing)
        .filter(
            Hearing.is_deleted.is_(False),
            or_(Hearing.outcome_confidence.is_(None), Hearing.outcome_confidence < threshold, Hearing.outcome_type == HearingOutcomeType.OTHER),
        )
        .order_by(Hearing.date.desc(), Hearing.id.desc())
    )


def reprocess_stale_hearings(
    db: Session,
    *,
    parser_version: str | None = None,
    limit: int = 200,
) -> int:
    current_version = parser_version or get_settings().outcome_parser_version
    hearings = (
        db.query(Hearing)
        .filter(
            Hearing.is_deleted.is_(False),
            or_(Hearing.parser_version.is_(None), Hearing.parser_version != current_version, Hearing.outcome_confidence < get_settings().default_outcome_confidence_verify),
        )
        .order_by(Hearing.updated_at.asc())
        .limit(limit)
        .all()
    )
    reprocessed = 0
    for hearing in hearings:
        reprocess_hearing(db, hearing=hearing, parser_version=current_version, explanation="Scheduled parser refresh")
        reprocessed += 1
    db.commit()
    return reprocessed