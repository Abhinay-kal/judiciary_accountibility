from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from itertools import combinations
from typing import Iterable, Sequence

from rapidfuzz import fuzz
from sqlalchemy import Float, String, bindparam, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.monitoring import JUDGE_AMBIGUOUS_SOURCE_TOTAL, JUDGE_PROVISIONAL_CREATED_TOTAL
from app.models import Court, JudgeAssignmentRole, JudgeRegistry

_HONORIFIC_RE = re.compile(
    r"\b(hon'?ble|honourable|mr\.?|mrs\.?|ms\.?|dr\.?|justice|justices|jj\.?|j\.?|chief\s+justice)\b",
    re.IGNORECASE,
)
_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]")
_CORAM_RE = re.compile(r"^\s*coram\s*[:\-]\s*", re.IGNORECASE)
_BENCH_JOIN_RE = re.compile(r"\s*(?:,|&| and |/|\|)\s*", re.IGNORECASE)


@dataclass
class CandidateScore:
    judge_id: str
    canonical_name: str
    score: float
    match_type: str


@dataclass
class AttributionResult:
    judge_id: str | None
    score: float
    match_type: str
    candidate_list: list[CandidateScore]


@dataclass
class BenchToken:
    raw_name: str
    sequence_index: int
    role: JudgeAssignmentRole
    is_presiding: bool


@dataclass
class AssignmentPayload:
    judge_registry_id: str
    judge_name_raw: str
    role: JudgeAssignmentRole
    is_presiding: bool
    sequence_index: int
    attribution_confidence: float
    matched_on: str
    metadata_json: dict


def normalize_name(raw_name: str) -> str:
    text = unicodedata.normalize("NFKC", raw_name or "").casefold()
    text = _CORAM_RE.sub("", text)
    text = _HONORIFIC_RE.sub(" ", text)
    text = _NON_WORD_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


@lru_cache(maxsize=4096)
def phonetic_key(name: str) -> str:
    normalized = normalize_name(name)
    if not normalized:
        return ""
    raw_tokens = [token for token in normalized.split() if token]
    merged_tokens: list[str] = []
    initials = ""
    for token in raw_tokens:
        if len(token) == 1:
            initials += token
            continue
        if initials:
            merged_tokens.append(initials)
            initials = ""
        merged_tokens.append(token)
    if initials:
        merged_tokens.append(initials)

    token_keys = [_soundex(token) for token in merged_tokens if token]
    return "-".join(token_keys)


def generate_name_variants(name: str) -> list[str]:
    normalized = normalize_name(name)
    if not normalized:
        return []
    tokens = normalized.split()
    variants = {normalized}
    if len(tokens) > 1:
        initials = " ".join([f"{token[0]}." for token in tokens[:-1]] + [tokens[-1]])
        variants.add(initials)
        variants.add(" ".join(tokens[::-1]))
    variants.add(" ".join(token for token in tokens if len(token) > 1))
    return sorted(value for value in variants if value)


def parse_bench_string(raw_bench: str | None) -> list[BenchToken]:
    if not raw_bench:
        return []
    cleaned = _CORAM_RE.sub("", raw_bench)
    lowered = cleaned.casefold()
    if "bench not constituted" in lowered:
        return []

    role = JudgeAssignmentRole.JUDGE_MEMBER
    if "single bench" in lowered:
        role = JudgeAssignmentRole.PRESIDING
    elif "division bench" in lowered:
        role = JudgeAssignmentRole.CO_JUDGE

    parts = [part.strip() for part in _BENCH_JOIN_RE.split(cleaned) if part.strip()]
    tokens: list[BenchToken] = []
    for idx, part in enumerate(parts):
        normalized = normalize_name(part)
        if not normalized:
            continue
        is_presiding = idx == 0
        token_role = JudgeAssignmentRole.PRESIDING if is_presiding else role
        tokens.append(
            BenchToken(
                raw_name=part.strip(),
                sequence_index=idx,
                role=token_role,
                is_presiding=is_presiding,
            )
        )
    return tokens


def candidate_lookup(
    db: Session,
    *,
    court_id: int | None,
    normalized_name: str,
    phonetic: str,
    hearing_date: datetime | None = None,
    designation: str | None = None,
    similarity_threshold: float = 0.30,
    max_candidate_pool: int = 30,
    limit: int = 10,
) -> list[CandidateScore]:
    sanitized_name = normalize_name((normalized_name or "").strip())
    if not sanitized_name or not _is_session_usable(db):
        return []

    threshold = max(0.0, min(1.0, float(similarity_threshold)))
    pool_size = max(1, int(max_candidate_pool))
    input_name_param = bindparam("input_name", sanitized_name, type_=String())
    similarity_threshold_param = bindparam("similarity_threshold", threshold, type_=Float())

    statement = select(JudgeRegistry).where(
        func.similarity(JudgeRegistry.name, input_name_param) > similarity_threshold_param
    )
    if court_id is not None:
        statement = statement.where((JudgeRegistry.court_id == court_id) | (JudgeRegistry.court_id.is_(None)))
    statement = statement.order_by(func.similarity(JudgeRegistry.name, input_name_param).desc()).limit(pool_size)

    try:
        candidates = list(db.scalars(statement))
    except SQLAlchemyError:
        return []

    scored: list[CandidateScore] = []
    for candidate in candidates:
        score, match_type = _score_candidate(
            normalized_name=sanitized_name,
            phonetic=phonetic,
            candidate=candidate,
            hearing_date=hearing_date,
            court_id=court_id,
            designation=designation,
        )
        if score <= 0:
            continue
        scored.append(
            CandidateScore(
                judge_id=candidate.judge_id,
                canonical_name=candidate.canonical_name,
                score=score,
                match_type=match_type,
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def resolve_judge(
    db: Session,
    *,
    raw_name: str,
    court_id: int | None,
    hearing_date: datetime | None = None,
    designation: str | None = None,
    similarity_threshold: float | None = None,
) -> AttributionResult:
    normalized = normalize_name((raw_name or "").strip())
    if not normalized or not _is_session_usable(db):
        return AttributionResult(
            judge_id=None,
            score=0.0,
            match_type="no_match",
            candidate_list=[],
        )

    settings = get_settings()
    threshold = similarity_threshold if similarity_threshold is not None else settings.judge_match_similarity_threshold
    phone = phonetic_key(normalized)
    candidates = candidate_lookup(
        db,
        court_id=court_id,
        normalized_name=normalized,
        phonetic=phone,
        hearing_date=hearing_date,
        designation=designation,
        similarity_threshold=threshold,
    )
    confidence_threshold = settings.judge_match_confidence_threshold
    if candidates and candidates[0].score >= confidence_threshold:
        winner = candidates[0]
        return AttributionResult(
            judge_id=winner.judge_id,
            score=winner.score,
            match_type=winner.match_type,
            candidate_list=candidates,
        )

    if settings.enable_judge_ml_matcher:
        from app.ml.judge_matcher import JudgeMLMatcher

        ml_suggestions = JudgeMLMatcher().suggest(raw_name, limit=5)
        if ml_suggestions:
            best = ml_suggestions[0]
            candidates.extend(
                CandidateScore(
                    judge_id=suggestion.judge_id,
                    canonical_name=suggestion.judge_id,
                    score=suggestion.score,
                    match_type=suggestion.match_type,
                )
                for suggestion in ml_suggestions
            )
            return AttributionResult(
                judge_id=best.judge_id,
                score=best.score,
                match_type=best.match_type,
                candidate_list=sorted(candidates, key=lambda item: item.score, reverse=True)[:10],
            )
    return AttributionResult(
        judge_id=None,
        score=candidates[0].score if candidates else 0.0,
        match_type=candidates[0].match_type if candidates else "no_match",
        candidate_list=candidates,
    )


def get_or_create_registry_entry(
    db: Session,
    *,
    raw_name: str,
    normalized_name: str,
    court_id: int | None,
    source_name: str,
    confidence: float,
    match_type: str,
) -> JudgeRegistry:
    existing = (
        db.query(JudgeRegistry)
        .filter(JudgeRegistry.canonical_name == normalized_name, JudgeRegistry.court_id == court_id)
        .first()
    )
    now = datetime.utcnow()
    if existing:
        existing.last_seen = now
        variants = set(existing.name_variants.get("variants", []))
        variants.update(generate_name_variants(raw_name))
        existing.name_variants = {"variants": sorted(variants)}
        return existing

    entry = JudgeRegistry(
        judge_id=str(uuid.uuid4()),
        canonical_name=normalized_name,
        name_variants={"variants": generate_name_variants(raw_name)},
        phonetic_keys={"keys": [phonetic_key(raw_name)]},
        court_id=court_id,
        known_designations={"values": []},
        first_seen=now,
        last_seen=now,
        metadata_json={
            "created_from_source": source_name,
            "creation_match_type": match_type,
            "creation_confidence": confidence,
            "raw_name": raw_name,
        },
        is_provisional=True,
    )
    db.add(entry)
    db.flush()
    JUDGE_PROVISIONAL_CREATED_TOTAL.labels(source=source_name).inc()
    return entry


def build_assignments_from_bench(
    db: Session,
    *,
    raw_bench: str | None,
    court_id: int | None,
    source_name: str,
    hearing_date: datetime | None,
) -> list[AssignmentPayload]:
    tokens = parse_bench_string(raw_bench)
    if raw_bench and not tokens:
        JUDGE_AMBIGUOUS_SOURCE_TOTAL.labels(source=source_name).inc()
    assignments: list[AssignmentPayload] = []
    for token in tokens:
        normalized = normalize_name(token.raw_name)
        attribution = resolve_judge(
            db,
            raw_name=token.raw_name,
            court_id=court_id,
            hearing_date=hearing_date,
        )
        if attribution.judge_id:
            judge_id = attribution.judge_id
        else:
            created = get_or_create_registry_entry(
                db,
                raw_name=token.raw_name,
                normalized_name=normalized,
                court_id=court_id,
                source_name=source_name,
                confidence=max(0.3, attribution.score),
                match_type=attribution.match_type,
            )
            judge_id = created.judge_id

        assignments.append(
            AssignmentPayload(
                judge_registry_id=judge_id,
                judge_name_raw=token.raw_name,
                role=token.role,
                is_presiding=token.is_presiding,
                sequence_index=token.sequence_index,
                attribution_confidence=max(attribution.score, 0.35 if attribution.judge_id is None else attribution.score),
                matched_on=attribution.match_type if attribution.match_type else "manual",
                metadata_json={
                    "normalized_name": normalized,
                    "candidate_list": [candidate.__dict__ for candidate in attribution.candidate_list],
                    "phonetic_key": phonetic_key(token.raw_name),
                },
            )
        )
    return assignments


def _score_candidate(
    *,
    normalized_name: str,
    phonetic: str,
    candidate: JudgeRegistry,
    hearing_date: datetime | None,
    court_id: int | None,
    designation: str | None,
) -> tuple[float, str]:
    candidate_name = normalize_name(candidate.canonical_name)
    if not candidate_name:
        return 0.0, "no_match"

    exact_match = 1.0 if normalized_name == candidate_name else 0.0
    token_overlap = _token_overlap(normalized_name, candidate_name)
    lev_similarity = fuzz.ratio(normalized_name, candidate_name) / 100.0
    threshold = get_settings().judge_match_levenshtein_threshold
    if lev_similarity < max(0.0, 1.0 - threshold - 0.5):
        lev_similarity = lev_similarity * 0.8

    candidate_phonetics = set(candidate.phonetic_keys.get("keys", []))
    phonetic_match = 1.0 if phonetic and phonetic in candidate_phonetics else 0.0

    court_match = 1.0 if court_id is not None and candidate.court_id == court_id else (0.4 if candidate.court_id is None else 0.0)

    tenure_score = 0.5
    if hearing_date is not None and candidate.first_seen and candidate.last_seen:
        hearing_ts = hearing_date if isinstance(hearing_date, datetime) else datetime.combine(hearing_date, datetime.min.time())
        tenure_score = 1.0 if candidate.first_seen <= hearing_ts <= candidate.last_seen else 0.2

    designation_match = 0.0
    if designation:
        known = {normalize_name(value) for value in candidate.known_designations.get("values", [])}
        designation_match = 1.0 if normalize_name(designation) in known else 0.0

    score = (
        0.30 * exact_match
        + 0.20 * token_overlap
        + 0.20 * lev_similarity
        + 0.10 * phonetic_match
        + 0.10 * court_match
        + 0.05 * tenure_score
        + 0.05 * designation_match
    )

    if exact_match >= 1.0:
        match_type = "exact"
    elif lev_similarity >= 0.9:
        match_type = "fuzzy"
    elif phonetic_match >= 1.0:
        match_type = "phonetic"
    elif tenure_score >= 1.0:
        match_type = "tenure"
    else:
        match_type = "manual"

    return score, match_type


def _token_overlap(a: str, b: str) -> float:
    left = set(a.split())
    right = set(b.split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _soundex(token: str) -> str:
    token = normalize_name(token)
    if not token:
        return ""
    first = token[0].upper()
    mapping = {
        **{letter: "1" for letter in "bfpv"},
        **{letter: "2" for letter in "cgjkqsxz"},
        **{letter: "3" for letter in "dt"},
        **{letter: "4" for letter in "l"},
        **{letter: "5" for letter in "mn"},
        **{letter: "6" for letter in "r"},
    }
    digits = []
    previous = ""
    for char in token[1:]:
        code = mapping.get(char, "")
        if code and code != previous:
            digits.append(code)
        previous = code
    result = (first + "".join(digits) + "000")[:4]
    return result


def _is_session_usable(db: Session | None) -> bool:
    if db is None:
        return False
    try:
        db.get_bind()
    except Exception:
        return False
    return True


def raw_bench_snapshot_id(raw_bench: str | None) -> str | None:
    if not raw_bench:
        return None
    return hashlib.sha256(raw_bench.encode("utf-8")).hexdigest()


def suggest_registry_merges(db: Session, *, limit: int = 100) -> list[dict]:
    provisional = (
        db.query(JudgeRegistry)
        .filter(JudgeRegistry.is_provisional.is_(True))
        .order_by(JudgeRegistry.updated_at.desc())
        .limit(limit)
        .all()
    )
    suggestions: list[dict] = []
    for left, right in combinations(provisional, 2):
        left_name = normalize_name(left.canonical_name)
        right_name = normalize_name(right.canonical_name)
        if not left_name or not right_name:
            continue
        score = fuzz.ratio(left_name, right_name) / 100.0
        if left.court_id is not None and left.court_id == right.court_id:
            score += 0.05
        if phonetic_key(left_name) == phonetic_key(right_name):
            score += 0.05
        if score >= 0.85:
            suggestions.append(
                {
                    "target_judge_id": left.judge_id,
                    "candidate_judge_id": right.judge_id,
                    "score": min(score, 0.99),
                    "target_name": left.canonical_name,
                    "candidate_name": right.canonical_name,
                }
            )
    suggestions.sort(key=lambda item: item["score"], reverse=True)
    return suggestions[:limit]
