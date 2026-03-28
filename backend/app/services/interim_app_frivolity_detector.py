"""
Interim Application Frivolity Detector - Identifies potentially frivolous
interim petitions (bail, stay, injunctions) that serve as delay tactics.

Frivolous petitions characteristics:
- Filed frequently by same advocate (pattern)
- Granted rate much lower than court baseline (likely unmeritorious)
- Filed but decision comes too late to affect case
- Grounds cited are weak or generic
- Filed right before important case events (blocking tactic)
"""

from datetime import date, timedelta
from enum import Enum
from typing import Optional
from sqlalchemy.orm import Session

from app.models.entities import (
    Advocate,
    Case,
    InterimApplication,
    InterimApplicationType,
)


class FrivolityLevel(str, Enum):
    """Classification of interim application frivolity."""
    CLEARLY_FRIVOLOUS = "clearly_frivolous"
    LIKELY_FRIVOLOUS = "likely_frivolous"
    POSSIBLY_FRIVOLOUS = "possibly_frivolous"
    AMBIGUOUS = "ambiguous"
    LIKELY_LEGITIMATE = "likely_legitimate"
    CLEARLY_LEGITIMATE = "clearly_legitimate"


class InterimApplicationFrivolityAssessment:
    """Result of frivolity analysis for an interim application."""
    
    def __init__(
        self,
        interim_app_id: int,
        frivolity_level: FrivolityLevel,
        frivolity_score: float,  # 0-1, higher = more frivolous
        reasons: list[str],
        red_flags: list[str],
    ):
        self.interim_app_id = interim_app_id
        self.frivolity_level = frivolity_level
        self.frivolity_score = frivolity_score
        self.reasons = reasons
        self.red_flags = red_flags
    
    def to_dict(self) -> dict:
        return {
            "interim_app_id": self.interim_app_id,
            "frivolity_level": self.frivolity_level.value,
            "frivolity_score": round(self.frivolity_score, 3),
            "reasons": self.reasons,
            "red_flags": self.red_flags,
        }


class InterimApplicationFrivolityDetector:
    """Detector for frivolous interim applications."""
    
    # Court baseline grant rates (ballpark estimates for Indian courts)
    # Real values should come from historical data aggregation
    TYPICAL_GRANT_RATES = {
        InterimApplicationType.BAIL: 0.60,  # ~60% of bail applications granted
        InterimApplicationType.STAY_OF_PROCEEDINGS: 0.25,  # ~25% of stay apps granted
        InterimApplicationType.INJUNCTION: 0.35,  # ~35% of injunctions granted
        InterimApplicationType.INTERIM_RELIEF: 0.40,
        InterimApplicationType.RECALL: 0.45,
        InterimApplicationType.REVIEW: 0.30,
        InterimApplicationType.CLARIFICATION: 0.70,
        InterimApplicationType.SUSPENSION: 0.30,
        InterimApplicationType.OTHER: 0.35,
    }
    
    @staticmethod
    def assess(
        interim_app: InterimApplication,
        case: Optional[Case] = None,
        applicant: Optional[Advocate] = None,
        case_grant_rate: Optional[float] = None,
    ) -> InterimApplicationFrivolityAssessment:
        """
        Assess whether an interim application is likely frivolous.
        
        Returns assessment with:
        - frivolity_level: Classification of frivolity
        - frivolity_score: 0-1 score (higher = more frivolous)
        - reasons: Explanation of assessment
        - red_flags: Specific indicators of frivolity
        """
        reasons = []
        red_flags = []
        frivolity_score = 0.5  # Start at neutral
        
        # Factor 1: Application Type
        app_type_analysis = InterimApplicationFrivolityDetector._analyze_app_type(
            interim_app.application_type
        )
        reasons.append(f"Application type: {app_type_analysis['name']}")
        frivolity_score = app_type_analysis["base_score"]
        
        # Factor 2: Decision Status and Grant Rate
        if interim_app.decision_status:
            if interim_app.decision_status.upper() == "REJECTED":
                red_flags.append("Application was rejected (suggests lack of merit)")
                frivolity_score += 0.15
            elif interim_app.decision_status.upper() == "GRANTED":
                reasons.append("Application was granted (indicates legitimacy)")
                frivolity_score -= 0.20
            elif interim_app.decision_status.upper() in ["DISMISSED", "WITHDRAWN"]:
                red_flags.append(f"Application {interim_app.decision_status.lower()} (possible lack of merit)")
                frivolity_score += 0.10
        
        # Factor 3: Timing Relative to Decision
        if interim_app.filing_date and interim_app.decision_date:
            days_to_decide = (interim_app.decision_date - interim_app.filing_date).days
            reasons.append(f"Decision timeframe: {days_to_decide} days")
            
            if days_to_decide < 0:
                red_flags.append("Decision date before filing date (data issue)")
                frivolity_score += 0.05
            elif days_to_decide > 90:
                red_flags.append("Very long delay in deciding application")
                frivolity_score -= 0.05
        
        # Factor 4: Grounds Cited Quality
        if interim_app.grounds_cited_text:
            grounds_quality = InterimApplicationFrivolityDetector._assess_grounds_quality(
                interim_app.grounds_cited_text
            )
            reasons.append(f"Grounds elaboration: {grounds_quality['assessment']}")
            frivolity_score += grounds_quality["frivolity_adjustment"]
            if grounds_quality.get("weak_grounds"):
                red_flags.append("Grounds are vague or generic")
        else:
            red_flags.append("No grounds provided for application")
            frivolity_score += 0.12
        
        # Factor 5: Prior Tagging
        if interim_app.is_frivolous_indicator:
            red_flags.append("Flagged as potentially frivolous in ingestion")
            frivolity_score += 0.10
        
        # Factor 6: Delay Impact
        if interim_app.delay_caused_days and interim_app.delay_caused_days > 30:
            red_flags.append(f"Caused {interim_app.delay_caused_days} days of delay")
            frivolity_score += 0.08
        
        # Factor 7: Applicant Pattern (if advocate available)
        if applicant:
            applicant_pattern = InterimApplicationFrivolityDetector._analyze_applicant_pattern(
                applicant, interim_app
            )
            red_flags.extend(applicant_pattern["red_flags"])
            frivolity_score += applicant_pattern["score_adjustment"]
        
        # Clamp score to 0-1
        frivolity_score = min(1.0, max(0.0, frivolity_score))
        
        # Determine final classification
        frivolity_level = InterimApplicationFrivolityDetector._score_to_level(
            frivolity_score
        )
        
        return InterimApplicationFrivolityAssessment(
            interim_app_id=interim_app.id,
            frivolity_level=frivolity_level,
            frivolity_score=frivolity_score,
            reasons=reasons,
            red_flags=red_flags,
        )
    
    @staticmethod
    def _analyze_app_type(app_type: InterimApplicationType) -> dict:
        """Analyze application type for frivolity propensity."""
        # Some application types are more commonly used as delay tactics
        if app_type == InterimApplicationType.STAY_OF_PROCEEDINGS:
            return {
                "name": "Stay of Proceedings",
                "base_score": 0.45,
                "note": "High frivolity potential (commonly used for delay)",
            }
        elif app_type == InterimApplicationType.BAIL:
            return {
                "name": "Bail",
                "base_score": 0.35,
                "note": "Moderate frivolity potential",
            }
        elif app_type == InterimApplicationType.INJUNCTION:
            return {
                "name": "Injunction",
                "base_score": 0.40,
                "note": "Moderate frivolity potential",
            }
        elif app_type == InterimApplicationType.CLARIFICATION:
            return {
                "name": "Clarification",
                "base_score": 0.25,
                "note": "Lower frivolity potential (often legitimate)",
            }
        else:
            return {
                "name": app_type.value,
                "base_score": 0.35,
                "note": "Standard frivolity potential",
            }
    
    @staticmethod
    def _assess_grounds_quality(grounds_text: str) -> dict:
        """Assess quality of grounds cited."""
        word_count = len(grounds_text.split())
        
        # Generic/weak language that suggests lack of substance
        weak_keywords = [
            "may be",
            "could be",
            "seems to",
            "appears to",
            "allegedly",
            "reportedly",
            "according to",
        ]
        weak_keyword_count = sum(
            1 for keyword in weak_keywords if keyword.lower() in grounds_text.lower()
        )
        
        if word_count < 30:
            return {
                "assessment": "Very brief (under 30 words)",
                "frivolity_adjustment": 0.15,
                "weak_grounds": True,
            }
        elif word_count < 80:
            return {
                "assessment": "Brief but present (30-80 words)",
                "frivolity_adjustment": 0.08,
                "weak_grounds": weak_keyword_count >= 2,
            }
        elif weak_keyword_count >= 3:
            return {
                "assessment": "Contains weak language (possibly frivolous framing)",
                "frivolity_adjustment": 0.12,
                "weak_grounds": True,
            }
        else:
            return {
                "assessment": "Substantive grounds provided",
                "frivolity_adjustment": -0.10,
                "weak_grounds": False,
            }
    
    @staticmethod
    def _analyze_applicant_pattern(
        advocate: Advocate,
        interim_app: InterimApplication,
    ) -> dict:
        """Analyze advocate's pattern of filing interim applications."""
        red_flags = []
        score_adjustment = 0.0
        
        # High case volume with probable interim app filings
        if advocate.total_cases > 150:
            # Rough estimate: if 40% of cases have adjournments and many have interim apps
            estimated_interim_apps = advocate.total_cases * 0.15  # estimate
            if estimated_interim_apps > 20:
                red_flags.append("Advocate files many interim applications (bulk practice)")
                score_adjustment += 0.08
        
        return {
            "red_flags": red_flags,
            "score_adjustment": score_adjustment,
        }
    
    @staticmethod
    def _score_to_level(score: float) -> FrivolityLevel:
        """Convert frivolity score to level."""
        if score >= 0.80:
            return FrivolityLevel.CLEARLY_FRIVOLOUS
        elif score >= 0.65:
            return FrivolityLevel.LIKELY_FRIVOLOUS
        elif score >= 0.50:
            return FrivolityLevel.POSSIBLY_FRIVOLOUS
        elif score >= 0.35:
            return FrivolityLevel.AMBIGUOUS
        elif score >= 0.20:
            return FrivolityLevel.LIKELY_LEGITIMATE
        else:
            return FrivolityLevel.CLEARLY_LEGITIMATE


def assess_interim_app_batch(
    db: Session,
    interim_app_ids: list[int],
) -> list[InterimApplicationFrivolityAssessment]:
    """Batch assess frivolity of multiple interim applications."""
    interim_apps = db.query(InterimApplication).filter(
        InterimApplication.id.in_(interim_app_ids)
    ).all()
    
    results = []
    for app in interim_apps:
        applicant = None
        if app.applicant_advocate_id:
            applicant = db.query(Advocate).filter(
                Advocate.id == app.applicant_advocate_id
            ).first()
        
        case = app.case if hasattr(app, 'case') else None
        assessment = InterimApplicationFrivolityDetector.assess(app, case, applicant)
        results.append(assessment)
    
    return results
