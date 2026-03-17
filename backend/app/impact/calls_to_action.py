from __future__ import annotations


def build_calls_to_action(*, audience: str, is_pending: bool) -> list[str]:
    common = [
        "Monitor progress through official case listings.",
        "Seek official status updates from authorized court channels.",
        "Support lawful transparency and open-data initiatives.",
    ]
    by_audience = {
        "journalists": ["Verify each reported claim against source orders and listing records."],
        "policymakers": ["Review court-level case-flow dashboards for targeted administrative reforms."],
        "legal_professionals": ["Track listing intervals and procedural adjournments for case-management strategy."],
        "civil_society": ["Use verified public records to advocate for process transparency."],
        "general_public": ["Follow updates through official records instead of unverified commentary."],
    }
    rows = common + by_audience.get(audience, by_audience["general_public"])
    if is_pending:
        rows.append("Revisit this case profile after major hearing updates.")
    return rows[:4]
