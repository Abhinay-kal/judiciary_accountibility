"""
Advocate Attribution Engine - Assigns responsibility for case delays to specific advocates.

Core principles:
1. Multi-factor attribution (can split responsibility across multiple parties)
2. Confidence scoring (avoid false accusations with low confidence)
3. Reversible attributions (update when new evidence emerges)
4. Transparent reasoning (explain why advocate is attributed responsibility)

Attribution methods:
- Direct: Advocate directly requested adjournment/interim app marked as tactic
- Pattern: Advocate's case pattern shows likely tactics
- Aggregate: Multiple minor indicators combined into responsibility score
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy.orm import Session

from app.models.entities import (
    Advocate,
    Adjournment,
    Case,
    CaseCounsel,
    InterimApplication,
)
from app.services.adjournment_classifier import (
    AdjournmentClassifier,
    AdjournmentTacticType,
)
from app.services.interim_app_frivolity_detector import (
    InterimApplicationFrivolityDetector,
    FrivolityLevel,
)


class AttributionType(str, Enum):
    """Type of delay attribution to an advocate."""
    ADJOURNMENT_TACTIC = "adjournment_tactic"
    FRIVOLOUS_INTERIM_APP = "frivolous_interim_app"
    PATTERN_BASED = "pattern_based"
    AGGREGATE = "aggregate"


class DelayAttribution:
    """Attribution of a case delay to an advocate."""
    
    def __init__(
        self,
        case_id: int,
        advocate_id: int,
        attribution_type: AttributionType,
        responsibility_percentage: float,  # 0-100
        confidence_score: float,  # 0-1
        impacted_days: int,
        supporting_evidence: dict,
        reasoning: str,
    ):
        self.case_id = case_id
        self.advocate_id = advocate_id
        self.attribution_type = attribution_type
        self.responsibility_percentage = responsibility_percentage
        self.confidence_score = confidence_score
        self.impacted_days = impacted_days
        self.supporting_evidence = supporting_evidence
        self.reasoning = reasoning
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "advocate_id": self.advocate_id,
            "attribution_type": self.attribution_type.value,
            "responsibility_percentage": round(self.responsibility_percentage, 1),
            "confidence_score": round(self.confidence_score, 3),
            "impacted_days": self.impacted_days,
            "supporting_evidence": self.supporting_evidence,
            "reasoning": self.reasoning,
        }


class AdvocateAttributionEngine:
    """Engine for attributing case delays to responsible advocates."""
    
    # Confidence thresholds for attribution
    HIGH_CONFIDENCE_THRESHOLD = 0.75  # Strong evidence
    MEDIUM_CONFIDENCE_THRESHOLD = 0.50  # Reasonable evidence
    LOW_CONFIDENCE_THRESHOLD = 0.30  # Weak evidence (requires caution)
    
    @staticmethod
    def attribute_case_delays(
        db: Session,
        case: Case,
        min_confidence: float = 0.50,
    ) -> list[DelayAttribution]:
        """
        Analyze a case and attribute delays to responsible advocates.
        
        Returns list of DelayAttribution objects, sorted by responsibility percentage.
        """
        attributions = []
        
        # Load related data
        case_counsel = db.query(CaseCounsel).filter(
            CaseCounsel.case_id == case.id
        ).all()
        adjournments = db.query(Adjournment).filter(
            Adjournment.case_id == case.id
        ).all()
        interim_apps = db.query(InterimApplication).filter(
            InterimApplication.case_id == case.id
        ).all()
        
        # Build advocate map for quick lookup
        advocate_ids = {cc.advocate_id for cc in case_counsel}
        advocates = {
            a.id: a for a in db.query(Advocate).filter(
                Advocate.id.in_(advocate_ids)
            ).all()
        }
        
        # Analyze adjournment-based tactics
        for adj in adjournments:
            if adj.requested_by and adj.requested_by in advocates:
                attr = AdvocateAttributionEngine._attribute_adjournment(
                    db, case, adj, advocates[adj.requested_by]
                )
                if attr and attr.confidence_score >= min_confidence:
                    attributions.append(attr)
        
        # Analyze interim app frivolity
        for interim_app in interim_apps:
            if (interim_app.applicant_advocate_id and
                interim_app.applicant_advocate_id in advocates):
                attr = AdvocateAttributionEngine._attribute_interim_app(
                    db, case, interim_app, advocates[interim_app.applicant_advocate_id]
                )
                if attr and attr.confidence_score >= min_confidence:
                    attributions.append(attr)
        
        # Pattern-based attribution (advocates showing systematic delay tactics)
        for advocate_id, advocate in advocates.items():
            pattern_attr = AdvocateAttributionEngine._attribute_by_pattern(
                db, case, advocate_id, adjournments, interim_apps
            )
            if pattern_attr and pattern_attr.confidence_score >= min_confidence:
                # Only add if not already attributed via direct evidence
                if not any(
                    a.advocate_id == advocate_id for a in attributions
                ):
                    attributions.append(pattern_attr)
        
        # Sort by responsibility percentage (descending)
        attributions.sort(
            key=lambda x: x.responsibility_percentage,
            reverse=True
        )
        
        return attributions
    
    @staticmethod
    def _attribute_adjournment(
        db: Session,
        case: Case,
        adj: Adjournment,
        advocate: Advocate,
    ) -> Optional[DelayAttribution]:
        """Attribute delay from a specific adjournment to its requester."""
        
        # Classify the adjournment
        classification = AdjournmentClassifier.classify(adj, case, advocate)
        
        # Only attribute if adjournment is flagged as likely/possible tactic
        if classification.tactic_type not in [
            AdjournmentTacticType.LIKELY_DELAY_TACTIC,
            AdjournmentTacticType.POSSIBLE_DELAY_TACTIC,
        ]:
            return None
        
        # Map confidence to percentage
        confidence = classification.tactic_confidence
        responsibility_percentage = confidence * 100
        
        # Estimate delay impact (adjournments typically cause 10-30 days)
        impacted_days = 15 if adj.hearing_id else 7
        
        reasoning = (
            f"Advocate {advocate.canonical_name} requested adjournment "
            f"(reason: {adj.reason_type.value if adj.reason_type else 'unspecified'}). "
            f"Classification: {classification.tactic_type.value} "
            f"(confidence: {confidence:.1%})"
        )
        
        return DelayAttribution(
            case_id=case.id,
            advocate_id=advocate.id,
            attribution_type=AttributionType.ADJOURNMENT_TACTIC,
            responsibility_percentage=responsibility_percentage,
            confidence_score=confidence,
            impacted_days=impacted_days,
            supporting_evidence={
                "adjournment_id": adj.id,
                "tactic_type": classification.tactic_type.value,
                "reason_type": adj.reason_type.value if adj.reason_type else None,
                "was_contested": adj.was_contested,
            },
            reasoning=reasoning,
        )
    
    @staticmethod
    def _attribute_interim_app(
        db: Session,
        case: Case,
        interim_app: InterimApplication,
        advocate: Advocate,
    ) -> Optional[DelayAttribution]:
        """Attribute delay from frivolous interim app to its applicant."""
        
        # Assess frivolity
        assessment = InterimApplicationFrivolityDetector.assess(
            interim_app, case, advocate
        )
        
        # Only attribute if flagged as likely/clearly frivolous
        if assessment.frivolity_level not in [
            FrivolityLevel.CLEARLY_FRIVOLOUS,
            FrivolityLevel.LIKELY_FRIVOLOUS,
        ]:
            return None
        
        # Map frivolity to responsibility
        frivolity_score = assessment.frivolity_score
        responsibility_percentage = frivolity_score * 100
        
        # Use actual delay if recorded, otherwise estimate
        impacted_days = interim_app.delay_caused_days or 20
        
        reasoning = (
            f"Advocate {advocate.canonical_name} filed {interim_app.application_type.value} "
            f"application. Assessment: {assessment.frivolity_level.value} "
            f"(frivolity score: {frivolity_score:.1%})"
        )
        
        return DelayAttribution(
            case_id=case.id,
            advocate_id=advocate.id,
            attribution_type=AttributionType.FRIVOLOUS_INTERIM_APP,
            responsibility_percentage=responsibility_percentage,
            confidence_score=frivolity_score,
            impacted_days=impacted_days,
            supporting_evidence={
                "interim_app_id": interim_app.id,
                "app_type": interim_app.application_type.value,
                "frivolity_level": assessment.frivolity_level.value,
                "decision_status": interim_app.decision_status,
            },
            reasoning=reasoning,
        )
    
    @staticmethod
    def _attribute_by_pattern(
        db: Session,
        case: Case,
        advocate_id: int,
        adjournments: list[Adjournment],
        interim_apps: list[InterimApplication],
    ) -> Optional[DelayAttribution]:
        """Attribute delay based on advocate's overall pattern in this case."""
        
        # Count tactic indicators from this advocate in this case
        advocate_adj_count = sum(
            1 for adj in adjournments
            if adj.requested_by == advocate_id
        )
        advocate_interim_count = sum(
            1 for app in interim_apps
            if app.applicant_advocate_id == advocate_id
        )
        
        total_indicators = advocate_adj_count + advocate_interim_count
        
        if total_indicators < 2:  # Need at least 2 indicators for pattern
            return None
        
        # Calculate pattern confidence based on frequency
        confidence = min(0.6, 0.2 + (total_indicators * 0.15))
        responsibility_percentage = confidence * 50  # Pattern attribution is partial
        
        # Estimate 5-10 days per indicator
        impacted_days = total_indicators * 7
        
        advocate = db.query(Advocate).filter(
            Advocate.id == advocate_id
        ).first()
        advocate_name = advocate.canonical_name if advocate else "Unknown"
        
        reasoning = (
            f"Pattern: Advocate {advocate_name} made {advocate_adj_count} adjournment requests "
            f"and {advocate_interim_count} interim applications in this case. "
            f"Pattern confidence: {confidence:.1%}"
        )
        
        return DelayAttribution(
            case_id=case.id,
            advocate_id=advocate_id,
            attribution_type=AttributionType.PATTERN_BASED,
            responsibility_percentage=responsibility_percentage,
            confidence_score=confidence,
            impacted_days=impacted_days,
            supporting_evidence={
                "adjournment_requests": advocate_adj_count,
                "interim_applications": advocate_interim_count,
            },
            reasoning=reasoning,
        )


def get_case_delay_attributions(
    db: Session,
    case_id: int,
    min_confidence: float = 0.50,
) -> list[DelayAttribution]:
    """Get all delay attributions for a specific case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return []
    
    return AdvocateAttributionEngine.attribute_case_delays(db, case, min_confidence)


def get_advocate_responsibility_summary(
    db: Session,
    advocate_id: int,
) -> dict:
    """Get summary of advocate's attributed responsibility."""
    query = db.query(Advocate).filter(Advocate.id == advocate_id).first()
    if not query:
        return {}
    
    # Note: In production, would query stored attributions from audit table
    # This is a simplified version for API response
    return {
        "advocate_id": advocate_id,
        "advocate_name": query.canonical_name,
        "total_cases": query.total_cases,
        "adjournment_request_count": query.total_adjournment_requests,
        "avg_adjournment_rate": query.avg_adjournment_rate,
        "note": "Full attribution data requires stored attribution records in database",
    }
