"""
Adjournment Classifier - Categorizes adjournments into tactic types.

Enables detection of deliberate delay tactics:
- Frivolous adjournments (requested without valid reason)
- Strategic adjournments (pattern of requesting specific adjournment types)
- Procedural adjournments (required by court/law)
- Legitimate adjournments (justified by circumstances)

Each classification generates a "tactic confidence" score (0-1) indicating
how likely the adjournment represents a deliberate delay tactic.
"""

from datetime import date
from enum import Enum
from typing import Optional
from sqlalchemy.orm import Session

from app.models.entities import (
    Adjournment,
    AdjournmentReasonType,
    Advocate,
    Case,
)


class AdjournmentTacticType(str, Enum):
    """Classification of adjournment likelihood as delay tactic."""
    LIKELY_DELAY_TACTIC = "likely_delay_tactic"
    POSSIBLE_DELAY_TACTIC = "possible_delay_tactic"
    AMBIGUOUS = "ambiguous"
    LIKELY_LEGITIMATE = "likely_legitimate"
    CLEARLY_NECESSARY = "clearly_necessary"


class AdjournmentClassification:
    """Result of adjournment classification analysis."""
    
    def __init__(
        self,
        adjournment_id: int,
        tactic_type: AdjournmentTacticType,
        tactic_confidence: float,  # 0-1 score
        reasons: list[str],
        risk_factors: list[str],
    ):
        self.adjournment_id = adjournment_id
        self.tactic_type = tactic_type
        self.tactic_confidence = tactic_confidence
        self.reasons = reasons
        self.risk_factors = risk_factors
    
    def to_dict(self) -> dict:
        return {
            "adjournment_id": self.adjournment_id,
            "tactic_type": self.tactic_type.value,
            "tactic_confidence": round(self.tactic_confidence, 3),
            "reasons": self.reasons,
            "risk_factors": self.risk_factors,
        }


class AdjournmentClassifier:
    """Classifier for adjournment tactic detection."""
    
    # CLEARLY_NECESSARY: Court-ordered, law-required, judge unavailable, etc.
    CLEARLY_NECESSARY_REASONS = {
        AdjournmentReasonType.COURT_ADJOURNED,
        AdjournmentReasonType.JUDGE_UNAVAILABLE,
        AdjournmentReasonType.COMPLIANCE_PENDING,
    }
    
    # LIKELY_LEGITIMATE: File/parties not ready (procedurally justified)
    LIKELY_LEGITIMATE_REASONS = {
        AdjournmentReasonType.FILE_NOT_READY,
        AdjournmentReasonType.PARTY_NOT_READY,
        AdjournmentReasonType.COUNSEL_UNAVAILABLE,
    }
    
    # POSSIBLE_DELAY_TACTIC: Interim pending (could be strategic)
    AMBIGUOUS_REASONS = {
        AdjournmentReasonType.INTERIM_PENDING,
        AdjournmentReasonType.OTHER_PROCEDURAL,
    }
    
    # LIKELY_DELAY_TACTIC: On request (by counsel) with no clear justification
    TACTIC_REASONS = {
        AdjournmentReasonType.ON_REQUEST,
        AdjournmentReasonType.UNSPECIFIED,
    }
    
    @staticmethod
    def classify(
        adjournment: Adjournment,
        case: Optional[Case] = None,
        advocate: Optional[Advocate] = None,
    ) -> AdjournmentClassification:
        """
        Classify an adjournment as a potential delay tactic.
        
        Returns an AdjournmentClassification object with:
        - tactic_type: Statistical classification
        - tactic_confidence: 0-1 score of tactic likelihood
        - reasons: Explanation of classification
        - risk_factors: Specific indicators increasing tactic probability
        """
        reasons = []
        risk_factors = []
        base_confidence = 0.5
        
        # Factor 1: Reason Type
        if adjournment.reason_type:
            reason_classification = AdjournmentClassifier._classify_by_reason(
                adjournment.reason_type
            )
            reasons.append(f"Reason type: {reason_classification['name']}")
            base_confidence = reason_classification["base_confidence"]
            if reason_classification.get("is_tactic_indicator"):
                risk_factors.append("Reason type associated with delay tactics")
        else:
            reasons.append("Reason type not specified")
            base_confidence = 0.65
            risk_factors.append("Missing reason specification")
        
        # Factor 2: Who Requested It
        if adjournment.requested_by:
            if advocate and advocate.id == adjournment.requested_by:
                reasons.append(f"Requested by advocate: {advocate.canonical_name}")
                # Advocate-requested adjournments are higher risk for tactics
                base_confidence += 0.15
                risk_factors.append("Advocate-initiated adjournment")
        
        # Factor 3: Was it Contested?
        if adjournment.was_contested:
            reasons.append("Adjournment was contested by opposing party")
            # Contested adjournments are less likely to be accepted tactics
            base_confidence -= 0.10
        
        # Factor 4: Grounds Citation
        if adjournment.grounds_cited_text:
            grounds_word_count = len(adjournment.grounds_cited_text.split())
            if grounds_word_count < 10:
                risk_factors.append("Minimal grounds cited (potential lack of justification)")
                base_confidence += 0.08
            reasons.append(f"Grounds cited ({grounds_word_count} words)")
        else:
            risk_factors.append("No grounds cited for adjournment")
            base_confidence += 0.10
        
        # Factor 5: Pattern Analysis (if advocate provided)
        if advocate:
            pattern_adjustment = AdjournmentClassifier._analyze_advocate_pattern(
                advocate, adjournment
            )
            if pattern_adjustment["risk_multiplier"] > 1.0:
                risk_factors.extend(pattern_adjustment["risk_factors"])
                base_confidence *= pattern_adjustment["risk_multiplier"]
        
        # Clamp confidence to 0-1
        tactic_confidence = min(1.0, max(0.0, base_confidence))
        
        # Determine final classification
        tactic_type = AdjournmentClassifier._confidence_to_type(tactic_confidence)
        
        return AdjournmentClassification(
            adjournment_id=adjournment.id,
            tactic_type=tactic_type,
            tactic_confidence=tactic_confidence,
            reasons=reasons,
            risk_factors=risk_factors,
        )
    
    @staticmethod
    def _classify_by_reason(reason_type: AdjournmentReasonType) -> dict:
        """Classify adjournment based on reason type."""
        if reason_type in AdjournmentClassifier.CLEARLY_NECESSARY_REASONS:
            return {
                "name": "Clearly Necessary",
                "base_confidence": 0.1,
                "is_tactic_indicator": False,
            }
        elif reason_type in AdjournmentClassifier.LIKELY_LEGITIMATE_REASONS:
            return {
                "name": "Likely Legitimate",
                "base_confidence": 0.3,
                "is_tactic_indicator": False,
            }
        elif reason_type in AdjournmentClassifier.AMBIGUOUS_REASONS:
            return {
                "name": "Ambiguous",
                "base_confidence": 0.5,
                "is_tactic_indicator": True,
            }
        elif reason_type in AdjournmentClassifier.TACTIC_REASONS:
            return {
                "name": "Potentially Tactical",
                "base_confidence": 0.7,
                "is_tactic_indicator": True,
            }
        else:
            return {
                "name": "Unknown",
                "base_confidence": 0.5,
                "is_tactic_indicator": True,
            }
    
    @staticmethod
    def _analyze_advocate_pattern(
        advocate: Advocate,
        adjournment: Adjournment,
    ) -> dict:
        """Analyze advocate's adjournment pattern."""
        risk_factors = []
        risk_multiplier = 1.0
        
        # High adjournment rate pattern
        if advocate.avg_adjournment_rate:
            if advocate.avg_adjournment_rate > 0.60:  # >60% of cases have adjournments
                risk_factors.append("Advocate has high adjournment rate (>60%)")
                risk_multiplier *= 1.15
            elif advocate.avg_adjournment_rate > 0.40:
                risk_factors.append("Advocate has elevated adjournment rate (>40%)")
                risk_multiplier *= 1.08
        
        # High case volume suggests possible pattern matching
        if advocate.total_cases > 100:
            risk_factors.append("Advocate handles many cases (bulk practice)")
            risk_multiplier *= 1.05
        
        return {
            "risk_multiplier": risk_multiplier,
            "risk_factors": risk_factors,
        }
    
    @staticmethod
    def _confidence_to_type(confidence: float) -> AdjournmentTacticType:
        """Convert confidence score to tactic type."""
        if confidence >= 0.75:
            return AdjournmentTacticType.LIKELY_DELAY_TACTIC
        elif confidence >= 0.60:
            return AdjournmentTacticType.POSSIBLE_DELAY_TACTIC
        elif confidence >= 0.40:
            return AdjournmentTacticType.AMBIGUOUS
        elif confidence >= 0.20:
            return AdjournmentTacticType.LIKELY_LEGITIMATE
        else:
            return AdjournmentTacticType.CLEARLY_NECESSARY


def classify_adjournement_batch(
    db: Session,
    adjournment_ids: list[int],
) -> list[AdjournmentClassification]:
    """Classify multiple adjournments in batch."""
    adjournments = db.query(Adjournment).filter(
        Adjournment.id.in_(adjournment_ids)
    ).all()
    
    results = []
    for adj in adjournments:
        advocate = None
        if adj.requested_by:
            advocate = db.query(Advocate).filter(
                Advocate.id == adj.requested_by
            ).first()
        
        case = adj.case if hasattr(adj, 'case') else None
        classification = AdjournmentClassifier.classify(adj, case, advocate)
        results.append(classification)
    
    return results
