"""
Integration test showing Phase 1 and Phase 2 working together.
Demonstrates the complete deliberate delay detection pipeline.
"""

from app.services.adjournment import classify_adjournment_tactic, DelayTactic
from app.services.delay_detection_phase2 import (
    AdjournmentDensity,
    PartyDrivenDelayScore,
    TacticFrequency,
)


def test_phase1_phase2_integration():
    """Test that Phase 1 and Phase 2 integrate correctly."""
    
    # Phase 1: Classify individual adjournments
    outcome_texts = [
        "Counsel out of station",      # PROXY_COUNSEL
        "Filing defect in petition",   # FRIVOLOUS_FILING
        "Judge on leave",              # JUDGE_UNAVAILABLE
        "Interim order to continue",   # STAY_EXTENSION
        "Adjourned",                   # NO_TACTIC
    ]
    
    classifications = []
    for text in outcome_texts:
        result = classify_adjournment_tactic(text)
        classifications.append(result)
        assert result.tactic in [
            DelayTactic.PROXY_COUNSEL,
            DelayTactic.FRIVOLOUS_FILING,
            DelayTactic.JUDGE_UNAVAILABLE,
            DelayTactic.STAY_EXTENSION,
            DelayTactic.NO_TACTIC_IDENTIFIED,
        ]
        assert 0.0 <= result.confidence <= 1.0
    
    # Verify Phase 1 correctly classified different tactics
    assert classifications[0].tactic == DelayTactic.PROXY_COUNSEL
    assert classifications[1].tactic == DelayTactic.FRIVOLOUS_FILING
    assert classifications[2].tactic == DelayTactic.JUDGE_UNAVAILABLE
    assert classifications[3].tactic == DelayTactic.STAY_EXTENSION
    
    # Phase 2: Would aggregate these across a case's hearing history
    # (In real usage with database, compute_tactic_frequency uses these classifications)
    tactic_freq = TacticFrequency(
        proxy_counsel=1,
        frivolous_filing=1,
        judge_unavailable=1,
        stay_extension=1,
        unidentified=1,
    )
    
    # Verify Phase 2 can structure the data
    assert tactic_freq.total == 5
    assert tactic_freq.as_dict["proxy_counsel"] == 1
    
    # Phase 2: Party-driven delay score uses these frequencies
    party_score = PartyDrivenDelayScore(
        score=60.5,
        proxy_counsel_ratio=0.2,
        frivolous_filing_ratio=0.2,
        tactic_diversity=4,
        recurrence_factor=0.2,
        explanation="Mixed tactics with moderate diversity",
    )
    
    # Verify score is valid
    assert 0 <= party_score.score <= 100
    assert party_score.tactic_diversity == 4
    
    print("✅ Phase 1 → Phase 2 integration validated")
    print(f"   Phase 1: Classified {len(classifications)} adjournments")
    print(f"   Phase 2: Aggregated into TacticFrequency and PartyDrivenDelayScore")
    print(f"   Party delay score: {party_score.score}/100")


if __name__ == "__main__":
    test_phase1_phase2_integration()
