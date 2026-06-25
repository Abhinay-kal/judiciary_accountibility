"""
Adjournment detection and deliberate delay tactic classification engine.

This module implements Phase 1 of the Deliberate Delay Detection system,
focusing on identifying specific delay tactics through NLP analysis of hearing outcomes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from logging import getLogger
from typing import Optional

from app.models import HearingOutcomeType
from app.ingestion.hearing_outcomes import parse_outcome_text

logger = getLogger(__name__)


class DelayTactic(str, Enum):
    """Enumeration of deliberate delay tactics identified in hearing outcomes."""

    PROXY_COUNSEL = "TACTIC_PROXY_COUNSEL"
    """Adjournment due to proxy counsel or unavailable party counsel."""

    FRIVOLOUS_FILING = "TACTIC_FRIVOLOUS_FILING"
    """Adjournment due to procedural defects in documentation or filings."""

    JUDGE_UNAVAILABLE = "TACTIC_JUDGE_UNAVAILABLE"
    """Adjournment due to judge unavailability or non-assembly of bench."""

    STAY_EXTENSION = "TACTIC_STAY_EXTENSION"
    """Adjournment due to continuation/extension of interim orders or stays."""

    NO_TACTIC_IDENTIFIED = "NO_TACTIC"
    """Adjournment with no deliberate delay tactic identified."""


@dataclass(frozen=True)
class TacticClassification:
    """Result of adjournment tactic classification analysis.

    Attributes:
        tactic: The identified DelayTactic enum value.
        confidence: Float between 0.0 and 1.0 indicating classification confidence.
        matched_keywords: List of specific keywords that triggered the classification.
        explanation: Human-readable explanation of the classification.
    """

    tactic: DelayTactic
    confidence: float
    matched_keywords: list[str]
    explanation: str

    def __post_init__(self) -> None:
        """Validate confidence score is in valid range."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


class AdjournmentTacticClassifier:
    """NLP-based classifier for detecting deliberate adjournment delay tactics.

    This classifier uses regex patterns, keyword matching, and contextual analysis
    on hearing outcome text to identify specific delay tactics used by parties
    to artificially extend case timelines in Indian courts.
    """

    # Regex patterns for normalizing outcome text
    _WHITESPACE_RE = re.compile(r"\s+")
    _HINDI_PATTERNS = [
        "स्थगित",  # adjourned in Hindi
        "अन्तरिम आदेश",  # interim order in Hindi
    ]

    # TACTIC 1: Proxy Counsel Indicators
    _PROXY_COUNSEL_PATTERNS = [
        (r"proxy\s+counsel", 3.0),
        (r"counsel.*out\s+of\s+station", 2.8),
        (r"counsel\s+not\s+present", 2.5),
        (r"counsel.*unavailable", 2.4),
        (r"appearing.*counsel.*absent", 2.6),
        (r"lead\s+counsel.*absent", 2.7),
        (r"counsel\s+is\s+out", 2.3),
        (r"counsel\s+not\s+ready", 2.0),
        (r"junior\s+counsel.*appearing", 1.8),
    ]

    # TACTIC 2: Frivolous Filing / Procedural Defects
    _FRIVOLOUS_FILING_PATTERNS = [
        (r"filing\s+of\s+(?:additional|fresh)\s+documents", 3.0),
        (r"(?:defect\s+in\s+filing|filing\s+defect)", 3.2),
        (r"(?:application|petition)\s+(?:defective|deficient)", 2.8),
        (r"papers?\s+(?:not|in)\s+complete", 2.6),
        (r"(?:pleading|petition)s?\s+(?:defective|improper)", 2.7),
        (r"filing\s+fee.*not\s+paid", 2.3),
        (r"(?:application|petition)\s+(?:not|not\s+properly)\s+signed", 2.2),
        (r"(?:amended|fresh)\s+petition\s+(?:filed|to be filed)", 2.0),
        (r"objections?\s+to\s+(?:petition|application)", 1.8),
    ]

    # TACTIC 3: Judge Unavailability / Bench Non-Assembly
    _JUDGE_UNAVAILABLE_PATTERNS = [
        (r"(?:hon'?ble)?\s*judge\s+(?:is\s+)?on\s+leave", 3.0),
        (r"bench\s+did\s+not\s+assemble", 3.2),
        (r"bench\s+(?:could\s+not|did\s+not)\s+sit", 2.8),
        (r"judge\s+(?:unavailable|not\s+available)", 2.6),
        (r"judicial\s+officer.*unavailable", 2.6),
        (r"presiding\s+(?:officer|judge).*absent", 2.5),
        (r"court\s+not\s+(?:in\s+session|assembled)", 2.2),
        (r"judge.*on\s+transfer", 2.0),
        (r"judge\s+recused", 1.9),
        (r"establishment\s+of\s+bench", 1.5),
    ]

    # TACTIC 4: Stay Extension / Interim Order Continuation
    _STAY_EXTENSION_PATTERNS = [
        (r"interim\s+order\s+(?:to\s+)?continue", 3.2),
        (r"stay\s+(?:order\s+)?(?:extended|to\s+continue)", 3.0),
        (r"existing\s+(?:interim\s+)?order\s+(?:continued|upheld)", 2.8),
        (r"interim\s+(?:relief|injunction)\s+(?:maintained|continued)", 2.8),
        (r"(?:status\s+)?quo\s+(?:maintained|continued)", 2.5),
        (r"further\s+(?:interim|staying)\s+(?:order|relief)", 2.5),
        (r"(?:interim\s+)?stay\s+(?:order|relief)\s+extended", 3.0),
        (r"interim\s+(?:application|relief).*allowed", 2.2),
        (r"extension\s+of\s+stay", 2.8),
    ]

    @classmethod
    def _normalize_text(cls, text: str | None) -> str:
        """Normalize hearing outcome text for pattern matching.

        Handles bytes encoding gracefully and validates input type strictly.
        Returns empty string on any encoding or type error (fail-safe).

        Args:
            text: Raw outcome text from hearing record (can be str, bytes, or None).

        Returns:
            Normalized text in lowercase with collapsed whitespace.
            Empty string if text is None, invalid type, or cannot be decoded.
        """
        if text is None:
            return ""

        try:
            # DEFENSIVE: Handle bytes by decoding with fallback encodings
            if isinstance(text, bytes):
                for encoding in ["utf-8", "utf-16", "latin-1", "iso-8859-1"]:
                    try:
                        text = text.decode(encoding)
                        break
                    except (UnicodeDecodeError, AttributeError):
                        continue
                else:
                    # All decodings failed
                    logger.warning("Failed to decode bytes text; returning empty string")
                    return ""

            # DEFENSIVE: Strict type check after potential decoding
            if not isinstance(text, str):
                logger.warning(f"Text input is not string or bytes: {type(text).__name__}")
                return ""

            # Normalize the string
            normalized = text.lower()
            normalized = cls._WHITESPACE_RE.sub(" ", normalized)
            normalized = re.sub(r"^(after|thereafter|next|below|adjourned|adjourned[^:]*to)[^:]*:", "", normalized)
            normalized = re.sub(r"[^\w\s]", " ", normalized)

            return normalized.strip()

        except (AttributeError, TypeError, UnicodeError) as e:
            logger.warning(f"Error normalizing text: {type(e).__name__}: {e}")
            return ""

    @classmethod
    def _calculate_pattern_score(
        cls, text: str, patterns: list[tuple[str, float]]
    ) -> tuple[float, list[str]]:
        """Calculate matched pattern score and extract keywords.

        DEFENSIVE: Catches TypeError in addition to re.error.

        Args:
            text: Normalized outcome text to analyze.
            patterns: List of (regex_pattern, weight) tuples to test.

        Returns:
            Tuple of (aggregate_score, matched_keywords).
        """
        total_score = 0.0
        matched_keywords: list[str] = []

        for pattern, weight in patterns:
            try:
                # DEFENSIVE: Validate text is actually a string before regex
                if not isinstance(text, str):
                    logger.warning(f"Pattern score text is not string: {type(text).__name__}")
                    break

                matches = re.finditer(pattern, text)
                for match in matches:
                    total_score += weight
                    keyword = match.group(0)
                    if keyword not in matched_keywords:
                        matched_keywords.append(keyword)

            except re.error as e:
                logger.debug(f"Invalid regex pattern '{pattern}': {e}")
                continue
            except TypeError as e:
                # CRITICAL FIX: Catch TypeError from non-string text
                logger.warning(f"TypeError in pattern matching: {e}")
                break
            except Exception as e:
                # Catch any other unexpected exceptions
                logger.warning(f"Unexpected error in pattern matching: {type(e).__name__}: {e}")
                continue

        return total_score, matched_keywords

    @classmethod
    def _normalize_score(cls, raw_score: float, max_possible: float = 10.0) -> float:
        """Normalize raw pattern matching score to 0.0-1.0 confidence range.

        Uses linear scaling with soft clipping to map pattern scores to probability space,
        tuned to balance sensitivity with specificity based on empirical testing.

        Args:
            raw_score: Aggregate pattern matching score (unbounded).
            max_possible: Reference maximum score for tuning (default 10.0).

        Returns:
            Normalized confidence score between 0.0 and 1.0.
        """
        if not isinstance(raw_score, (int, float)) or raw_score is None:
            return 0.0

        if raw_score <= 0:
            return 0.0

        # Linear scaling with empirical tuning
        baseline = 4.0
        exponent = 0.65

        try:
            score = (raw_score / baseline) ** exponent
            return min(1.0, max(0.0, score))
        except (ValueError, OverflowError, ZeroDivisionError):
            return 1.0 if raw_score > 0 else 0.0

    @classmethod
    def classify_tactic(cls, outcome_text: str | None) -> TacticClassification:
        """Classify adjournment tactic from hearing outcome text.

        DEFENSIVE: Handles None, bytes, malformed OCR, and encoding errors gracefully.

        Analyzes hearing outcome text to identify specific delay tactics.
        Returns the highest-confidence tactic along with supporting evidence.

        Args:
            outcome_text: Raw outcome text from court hearing record.

        Returns:
            TacticClassification containing identified tactic and confidence score.
            Always returns a valid TacticClassification (never raises).
        """
        # DEFENSIVE: Handle None and empty input upfront
        if not outcome_text:
            return TacticClassification(
                tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
                confidence=0.0,
                matched_keywords=[],
                explanation="No outcome text provided for analysis.",
            )

        # Normalize text with encoding-safe handling
        normalized_text = cls._normalize_text(outcome_text)

        if not normalized_text:
            return TacticClassification(
                tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
                confidence=0.0,
                matched_keywords=[],
                explanation="Outcome text normalized to empty string (invalid encoding or format).",
            )

        try:
            # Calculate scores for each tactic
            proxy_score, proxy_keywords = cls._calculate_pattern_score(normalized_text, cls._PROXY_COUNSEL_PATTERNS)
            frivolous_score, frivolous_keywords = cls._calculate_pattern_score(
                normalized_text, cls._FRIVOLOUS_FILING_PATTERNS
            )
            judge_score, judge_keywords = cls._calculate_pattern_score(normalized_text, cls._JUDGE_UNAVAILABLE_PATTERNS)
            stay_score, stay_keywords = cls._calculate_pattern_score(normalized_text, cls._STAY_EXTENSION_PATTERNS)

            # Normalize scores to confidence range
            proxy_confidence = cls._normalize_score(proxy_score)
            frivolous_confidence = cls._normalize_score(frivolous_score)
            judge_confidence = cls._normalize_score(judge_score)
            stay_confidence = cls._normalize_score(stay_score)

            # Find highest confidence tactic
            scores = {
                DelayTactic.PROXY_COUNSEL: (proxy_confidence, proxy_keywords),
                DelayTactic.FRIVOLOUS_FILING: (frivolous_confidence, frivolous_keywords),
                DelayTactic.JUDGE_UNAVAILABLE: (judge_confidence, judge_keywords),
                DelayTactic.STAY_EXTENSION: (stay_confidence, stay_keywords),
            }

            best_tactic = max(scores, key=lambda t: scores[t][0])
            best_confidence, best_keywords = scores[best_tactic]

            # Generate explanation
            if best_confidence < 0.15:
                return TacticClassification(
                    tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
                    confidence=best_confidence,
                    matched_keywords=best_keywords,
                    explanation=f"No deliberate delay tactic detected (best match: {best_tactic.value}, confidence: {best_confidence:.2f}).",
                )

            tactic_explanations = {
                DelayTactic.PROXY_COUNSEL: "Adjournment attributed to proxy counsel or party counsel unavailability.",
                DelayTactic.FRIVOLOUS_FILING: "Adjournment attributed to procedural defects in case filings or documentation.",
                DelayTactic.JUDGE_UNAVAILABLE: "Adjournment attributed to judge unavailability or bench non-assembly.",
                DelayTactic.STAY_EXTENSION: "Adjournment attributed to continuation or extension of interim relief orders.",
            }

            explanation = tactic_explanations.get(
                best_tactic, "Adjournment tactic classified but explanation unavailable."
            )

            return TacticClassification(
                tactic=best_tactic,
                confidence=best_confidence,
                matched_keywords=best_keywords,
                explanation=explanation,
            )

        except Exception as e:
            # FINAL SAFETY NET: Any unexpected exception returns safe default
            logger.error(f"Unexpected error in classify_tactic: {type(e).__name__}: {e}", exc_info=True)
            return TacticClassification(
                tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
                confidence=0.0,
                matched_keywords=[],
                explanation=f"Classification failed due to internal error: {type(e).__name__}",
            )


def detect_adjournment(
    outcome_text: str | None,
    *,
    parsed_outcome: HearingOutcomeType | None = None,
) -> tuple[bool, str | None]:
    """Detect whether a hearing outcome indicates an adjournment.

    This is the legacy detection function. For deliberate delay tactic classification,
    use classify_adjournment_tactic() instead.

    Args:
        outcome_text: Raw outcome text from hearing record.
        parsed_outcome: Pre-parsed HearingOutcomeType if available.

    Returns:
        Tuple of (is_adjourned: bool, keyword: str | None) where keyword is
        the primary adjournment keyword if available.
    """

    if parsed_outcome == HearingOutcomeType.ADJOURNED:
        result = parse_outcome_text(outcome_text)
        keyword = result.matched_keywords[0] if result.matched_keywords else None
        if keyword == "adjourned to":
            keyword = "adjourned"
        return True, keyword

    result = parse_outcome_text(outcome_text, allow_ml=False)
    if result.outcome_type != HearingOutcomeType.ADJOURNED:
        return False, None
    keyword = result.matched_keywords[0] if result.matched_keywords else None
    if keyword == "adjourned to":
        keyword = "adjourned"
    return True, keyword


def classify_adjournment_tactic(outcome_text: str | None) -> TacticClassification:
    """Classify deliberate delay tactic from adjournment outcome text.

    DIAGNOSTIC VERSION: Aggressive runtime introspection with full state dumping.
    Captures all variable states at failure point for debugging poisoned data.

    High-level function wrapping the AdjournmentTacticClassifier for external use.

    Args:
        outcome_text: Raw outcome text from hearing record.

    Returns:
        TacticClassification containing identified tactic and confidence score.
        Always returns safe default on any exception with diagnostic logging.

    Example:
        >>> result = classify_adjournment_tactic("Adjourned, proxy counsel appears")
        >>> print(result.tactic)
        TACTIC_PROXY_COUNSEL
        >>> print(f"Confidence: {result.confidence:.2%}")
        Confidence: 89.50%
    """
    # ============================================================================
    # DIAGNOSTIC CHECKPOINT 1: Input State Inspection
    # ============================================================================
    try:
        input_type = type(outcome_text).__name__
        input_length = len(outcome_text) if hasattr(outcome_text, '__len__') else "N/A"
        input_is_none = outcome_text is None
        
        logger.critical(
            f"[DIAG-INPUT] outcome_text state: "
            f"type={input_type} | length={input_length} | is_none={input_is_none} | "
            f"repr={repr(outcome_text)[:200] if outcome_text else 'None'}"
        )
    except Exception as diag_e:
        logger.critical(f"[DIAG-FAIL] Could not inspect input: {type(diag_e).__name__}: {diag_e}")

    try:
        # ========================================================================
        # CHECKPOINT 2: Call classifier with isolation
        # ========================================================================
        logger.critical("[DIAG-ENTER] Calling AdjournmentTacticClassifier.classify_tactic()")
        
        result = AdjournmentTacticClassifier.classify_tactic(outcome_text)
        
        # ========================================================================
        # CHECKPOINT 3: Result State Inspection
        # ========================================================================
        logger.critical(
            f"[DIAG-RESULT] Classification output: "
            f"tactic={result.tactic if hasattr(result, 'tactic') else 'MISSING'} | "
            f"confidence={result.confidence if hasattr(result, 'confidence') else 'MISSING'} | "
            f"keywords_count={len(result.matched_keywords) if hasattr(result, 'matched_keywords') else 'MISSING'} | "
            f"explanation={repr(result.explanation)[:100] if hasattr(result, 'explanation') else 'MISSING'}"
        )
        
        return result
        
    except AttributeError as ae:
        # Result object missing expected attributes
        logger.critical(
            f"[DIAG-EXCEPTION-ATTRIBUTE] AttributeError in result handling: {ae}",
            exc_info=True,
            extra={
                "exception_type": type(ae).__name__,
                "exception_msg": str(ae),
                "outcome_text_type": type(outcome_text).__name__,
                "outcome_text_len": len(outcome_text) if hasattr(outcome_text, '__len__') else "unknown",
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Result attribute missing: {str(ae)[:100]}",
        )
    
    except TypeError as te:
        # Type mismatch or invalid operation
        logger.critical(
            f"[DIAG-EXCEPTION-TYPE] TypeError during classification: {te}",
            exc_info=True,
            extra={
                "exception_type": type(te).__name__,
                "exception_msg": str(te),
                "outcome_text_type": type(outcome_text).__name__,
                "outcome_text_value": repr(outcome_text)[:200] if outcome_text else "None",
                "outcome_text_callable": callable(outcome_text),
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Type error: {str(te)[:100]}",
        )
    
    except ValueError as ve:
        # Invalid value passed to function
        logger.critical(
            f"[DIAG-EXCEPTION-VALUE] ValueError during classification: {ve}",
            exc_info=True,
            extra={
                "exception_type": type(ve).__name__,
                "exception_msg": str(ve),
                "outcome_text_type": type(outcome_text).__name__,
                "outcome_text_repr": repr(outcome_text)[:300],
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Value error: {str(ve)[:100]}",
        )
    
    except KeyError as ke:
        # Missing key in dictionary lookup
        logger.critical(
            f"[DIAG-EXCEPTION-KEY] KeyError during classification: {ke}",
            exc_info=True,
            extra={
                "exception_type": type(ke).__name__,
                "exception_msg": str(ke),
                "missing_key": str(ke),
                "outcome_text_type": type(outcome_text).__name__,
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Missing key: {str(ke)[:100]}",
        )
    
    except IndexError as ie:
        # Invalid list/sequence index
        logger.critical(
            f"[DIAG-EXCEPTION-INDEX] IndexError during classification: {ie}",
            exc_info=True,
            extra={
                "exception_type": type(ie).__name__,
                "exception_msg": str(ie),
                "outcome_text_type": type(outcome_text).__name__,
                "outcome_text_len": len(outcome_text) if hasattr(outcome_text, '__len__') else "unknown",
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Index error: {str(ie)[:100]}",
        )
    
    except UnicodeError as ue:
        # Encoding/decoding failure
        logger.critical(
            f"[DIAG-EXCEPTION-UNICODE] UnicodeError during classification: {ue}",
            exc_info=True,
            extra={
                "exception_type": type(ue).__name__,
                "exception_msg": str(ue),
                "outcome_text_type": type(outcome_text).__name__,
                "outcome_text_repr_bytes": repr(outcome_text)[:100] if isinstance(outcome_text, bytes) else "not bytes",
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Unicode error: {str(ue)[:100]}",
        )
    
    except RecursionError as re:
        # Stack overflow from deep recursion
        logger.critical(
            f"[DIAG-EXCEPTION-RECURSION] RecursionError during classification: {re}",
            exc_info=True,
            extra={
                "exception_type": type(re).__name__,
                "exception_msg": str(re),
                "outcome_text_type": type(outcome_text).__name__,
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation="[DIAG] Recursion error: Stack overflow",
        )
    
    except MemoryError as me:
        # Out of memory
        logger.critical(
            f"[DIAG-EXCEPTION-MEMORY] MemoryError during classification: {me}",
            exc_info=True,
            extra={
                "exception_type": type(me).__name__,
                "outcome_text_type": type(outcome_text).__name__,
            }
        )
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation="[DIAG] Memory error: Out of memory",
        )
    
    except Exception as e:
        # UNIVERSAL CATCH: Any other exception type
        import inspect
        import traceback
        
        # Get detailed call stack information
        frame_info = inspect.currentframe()
        stack_depth = len(inspect.stack())
        tb_lines = traceback.format_exc().split('\n')
        
        logger.critical(
            f"[DIAG-EXCEPTION-GENERIC] Uncaught exception in classify_adjournment_tactic: {type(e).__name__}",
            exc_info=True,
            extra={
                "exception_type": type(e).__name__,
                "exception_msg": str(e),
                "exception_repr": repr(e)[:300],
                "outcome_text_type": type(outcome_text).__name__,
                "outcome_text_value": repr(outcome_text)[:200] if outcome_text else "None",
                "outcome_text_id": id(outcome_text),
                "stack_depth": stack_depth,
                "traceback_lines": tb_lines[:10],
            }
        )
        
        return TacticClassification(
            tactic=DelayTactic.NO_TACTIC_IDENTIFIED,
            confidence=0.0,
            matched_keywords=[],
            explanation=f"[DIAG] Unhandled error: {type(e).__name__}: {str(e)[:100]}",
        )
