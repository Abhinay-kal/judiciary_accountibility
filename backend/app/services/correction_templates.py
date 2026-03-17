AUTO_ACK_TEMPLATE = (
    "Subject: Correction request received\n\n"
    "We have received your correction request (ID: {request_id}). "
    "This acknowledgement confirms intake only. "
    "We aim to acknowledge within 48 hours and review within 14 days."
)

ADMIN_ACCEPT_TEMPLATE = (
    "Correction accepted. Public content has been updated to reflect a neutral summary "
    "and linked evidence. No accusation is implied by this update."
)

ADMIN_REJECT_TEMPLATE = (
    "Correction request reviewed and not accepted at this stage. "
    "Current publication remains data-status labeled with sources and confidence context."
)

PUBLIC_CORRECTION_NOTE_TEMPLATE = (
    "Update: A correction request was reviewed. Public text has been adjusted to ensure "
    "neutral wording and source-linked context."
)
