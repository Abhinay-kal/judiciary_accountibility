"""
RTI Request Templates - Compliant with RTI Act, 2005

Provides structured templates for generating legally valid RTI applications
for judicial transparency and case information requests.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from datetime import datetime


class RTIRequestType(str, Enum):
    """Types of RTI requests supported."""
    MISSING_CASE_RECORDS = "missing_case_records"
    TRANSFER_HISTORY = "transfer_history"
    HEARING_TRANSCRIPTS = "hearing_transcripts"
    PENDING_ORDERS_STATUS = "pending_orders_status"
    CASE_LISTING_DETAILS = "case_listing_details"
    ADMINISTRATIVE_DELAYS = "administrative_delays"
    DATA_DISCREPANCIES = "data_discrepancies"
    CUSTOM = "custom"


class CourtLevel(str, Enum):
    """Judicial hierarchy levels."""
    DISTRICT_COURT = "district_court"
    HIGH_COURT = "high_court"
    SUPREME_COURT = "supreme_court"


@dataclass
class CourtDetails:
    """Court identification for RTI targeting."""
    level: CourtLevel
    name: str
    state: str
    district: Optional[str] = None
    bench: Optional[str] = None


@dataclass
class CaseInfo:
    """Case-specific information for RTI context."""
    case_number: str
    year: int
    court_details: CourtDetails
    filed_date: Optional[datetime] = None
    case_type: Optional[str] = None
    parties: Optional[List[str]] = None


@dataclass
class ApplicantInfo:
    """RTI applicant details."""
    name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    email: Optional[str] = None
    phone: Optional[str] = None
    aadhar_optional: Optional[str] = None
    preferred_language: str = "English"


@dataclass
class RTITemplate:
    """Core RTI request template structure."""
    request_type: RTIRequestType
    case_info: CaseInfo
    applicant_info: ApplicantInfo
    specific_requests: List[str]
    declaration_accepted: bool = False
    preferred_pio_address: Optional[str] = None
    language: str = "English"


class RTITemplateLibrary:
    """Library of pre-composed RTI request templates."""

    # =========================================================================
    # TEMPLATE 1: MISSING CASE RECORDS
    # =========================================================================
    
    MISSING_CASE_RECORDS_TEMPLATE = """
RTI REQUEST FOR MISSING CASE RECORDS
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Certified Copies of Case Records
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Pursuant to the Right to Information Act, 2005, and the Information Seekers
Charter under the Judicial Transparency Initiative, I hereby request certified
copies of the following information and documents in the above-mentioned case:

REQUESTED INFORMATION:

1. Certified copy of the complete case file including:
   - Original plaint/petition with annexures
   - All written statements (reply, rejoinder, etc.)
   - All applications filed by either party with orders passed thereon
   - Copies of all orders passed by the Court since {from_date}

2. List of all hearing dates scheduled or conducted in this case, with:
   - Date of hearing
   - Status of proceedings (case called/adjourned/pending)
   - Cause of adjournment, if any

3. Details of case listing status:
   - Current status in cause list
   - Next date of hearing (if available)
   - Whether the case is alive or closed in Court records

4. Information regarding any transfers or remittals:
   - Whether the case has been transferred to another bench/court
   - If transferred, date and details of transfer order
   - Current location of case file

DECLARATION:

I am furnishing this request as an information seeker desirous to obtain
information in the public interest and to safeguard my legal rights. I am
aware of the implications of false declarations and undertake to provide
true and accurate information.

FEES & MODE OF DELIVERY:

I am ready to pay the applicable fees as per RTI Act Rules. Please inform
me of the fee amount for providing the above information. I prefer to
receive the information by: [SPECIFY: Post/Email/Personal Pickup]

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}
Preferred Language: {language}

I request that this application be acknowledged within 5 days of receipt
and the information be provided within 30 days as per Section 7 of the
RTI Act, 2005.

Sincerely,

({applicant_name})
[Attached: Case details, proof of identity]
"""

    # =========================================================================
    # TEMPLATE 2: TRANSFER HISTORY
    # =========================================================================
    
    TRANSFER_HISTORY_TEMPLATE = """
RTI REQUEST FOR CASE TRANSFER & REMITTAL HISTORY
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Complete Case Transfer & Remittal Records
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Pursuant to the Right to Information Act, 2005, I hereby request a
comprehensive chronological record of all transfers, remittals, and
jurisdictional movements of the above-mentioned case.

REQUESTED INFORMATION:

1. Complete transfer history including:
   a) Date of original filing and court of original jurisdiction
   b) All orders of transfer/remittal with dates (certified copies)
   c) Grounds/reasons stated in transfer orders
   d) Court to which the case was transferred and current location
   e) Whether case was remitted back, and if so, on what dates

2. Copies of all stay/suspension orders (if any) affecting case proceedings

3. Details of any territorial jurisdiction disputes or challenges:
   - Whether any challenge to jurisdiction was raised
   - Orders passed on jurisdiction challenges
   - Current status of jurisdiction determination

4. List of all courts through which this case has passed in chronological order

LEGAL BASIS:

This request is filed under the RTI Act, 2005, to obtain information
concerning judicial administration and the movement of a case through
the judicial system, which is information of public interest.

DECLARATION:

I, {applicant_name}, hereby declare that I am seeking this information
to understand the status and location of the case file and to ensure
proper judicial administration.

CONTACT & FEE DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

I am prepared to pay applicable fees and request acknowledgment within
5 days and response within 30 days of receipt of this application.

Sincerely,

({applicant_name})
"""

    # =========================================================================
    # TEMPLATE 3: HEARING TRANSCRIPTS & RECORDINGS
    # =========================================================================
    
    HEARING_TRANSCRIPTS_TEMPLATE = """
RTI REQUEST FOR HEARING TRANSCRIPTS & AUDIO RECORDINGS
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Hearing Proceedings Record & Audio Files
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Under the Right to Information Act, 2005, I hereby request copies of
hearing proceedings records and audio recordings for the case mentioned above.

REQUESTED INFORMATION:

1. Audio recordings of hearings:
   a) Whether audio/video recordings of court hearings are maintained
   b) If yes, copies of recordings of hearings held on: {hearing_dates}
   c) Format in which recordings are available (CD/USB/Digital)
   d) Applicable fee for obtaining copies

2. Court proceedings transcript/order sheet:
   a) Certified copies of order sheets for all hearings held since {from_date}
   b) Minutes of proceedings, if separately maintained
   c) Names of counsel/advocates who appeared and arguments noted

3. Details of court staff/judge:
   a) Name and designation of presiding officer for each hearing
   b) Whether court stenographer/recorder was present

4. Status of digitalization:
   a) Whether court proceedings are digitally recorded
   b) Accessibility to digital records
   c) Storage and preservation measures for audio files

DECLARATION:

I hereby declare that this request is made to obtain authentic records
of judicial proceedings to preserve evidence and ensure transparency in
the administration of justice.

MODE OF DELIVERY:

Please provide information in digital format (USB/Email) if available,
or in physical form as applicable.

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

I request acknowledgment within 5 days and response within 30 days as
per Section 7, RTI Act, 2005.

Sincerely,

({applicant_name})
"""

    # =========================================================================
    # TEMPLATE 4: PENDING ORDERS STATUS
    # =========================================================================
    
    PENDING_ORDERS_STATUS_TEMPLATE = """
RTI REQUEST FOR STATUS OF PENDING ORDERS
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Information on Pending Orders & Status
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Pursuant to the Right to Information Act, 2005, I hereby request information
regarding the current status and any pending orders in the above-named case.

REQUESTED INFORMATION:

1. Current status of pending orders:
   a) List of all orders reserved for judgment/decision
   b) Date on which each order was reserved
   c) Prescribed timeline for delivery of judgment
   d) Current status of deliberation/writing (if available)

2. Pending applications:
   a) List of applications pending before the court
   b) Date each application was filed
   c) Current status and reason for pendency
   d) Expected date of hearing/decision

3. Reasons for delay (if case is pending beyond normal timeline):
   a) Whether matter is pending due to technical/administrative reasons
   b) Whether case file is in the custody of the presiding officer
   c) Whether any additional time has been sought

4. Case calendar information:
   a) Next scheduled date of hearing
   b) Whether the case is fixed in the cause list
   c) Estimated time for final disposal based on court's pipeline

LEGAL FRAMEWORK:

This request is made to obtain crucial information affecting the timely
disposal of justice and to hold the judicial system accountable for
delays in case progression.

DECLARATION:

I declare that this information is sought to monitor the status of
proceedings and ensure constitutional right to speedy justice.

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

Hoping for acknowledgment within 5 days and response within 30 days of receipt.

Sincerely,

({applicant_name})
"""

    # =========================================================================
    # TEMPLATE 5: CASE LISTING DETAILS
    # =========================================================================
    
    CASE_LISTING_DETAILS_TEMPLATE = """
RTI REQUEST FOR CASE LISTING & CAUSE LIST DETAILS
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Historical Case Listing & Cause List Information
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Under the Right to Information Act, 2005, I hereby request complete
information regarding the listing and cause list history of the above case.

REQUESTED INFORMATION:

1. Case listing information:
   a) Copy of all cause lists in which the case has been listed
   b) Dates on which listed (with cause list identification number)
   c) Whether case was fixed for hearing, final arguments, or directions
   d) Whether case was adjourned and grounds for adjournment

2. Listing pattern and frequency:
   a) How many times has the case been relisted after adjournment
   b) Average time gap between consecutive listings
   c) Reason for frequent/infrequent listing

3. Cause list management:
   a) Criteria used for fixing cases in cause list
   b) Whether case follows any priority listing system
   c) Changes to listing status or priority status over time

4. Consolidated case history:
   a) Complete chronological listing of all dates case was before the court
   b) Outcome of each listing (adjourned/final hearing/orders passed)
   c) Attendees (counsel, parties, judges) for each hearing
   d) Key developments and milestones in case progression

DECLARATIONS:

I seek this information as a stakeholder in the justice system to understand
the pace of case disposal and judicial scheduling practices.

This request is made in the public interest to improve transparency in
the administration of the courts.

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

I shall be obliged if the court will acknowledge this request within 5 days
and furnish the information within 30 days as prescribed by the RTI Act.

Sincerely,

({applicant_name})
"""

    # =========================================================================
    # TEMPLATE 6: ADMINISTRATIVE DELAYS
    # =========================================================================
    
    ADMINISTRATIVE_DELAYS_TEMPLATE = """
RTI REQUEST FOR INFORMATION ON CASE DISPOSAL DELAYS
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Information Regarding Administrative & Case Delays
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Pursuant to the Right to Information Act, 2005, and the Supreme Court's
directives on judicial transparency, I hereby request information regarding
delays and administrative issues affecting the case mentioned above.

REQUESTED INFORMATION:

1. Causes of delay attribution:
   a) List of reasons for adjournments granted in this case
   b) Whether adjournments were granted at request of parties or court
   c) Any administrative/technical reasons for adjournments
   d) Whether any adjournment was opposed/granted against objection

2. Time analysis:
   a) Total time elapsed since filing until current date
   b) Time comparison with similar cases disposed in this court
   c) Benchmark time for similar case type in national standards
   d) Remaining estimated time to disposal (if available)

3. Judicial resources:
   a) Number of judges/benches handling this case type at the court
   b) Workload statistics for the presiding judge
   c) Whether judicial vacancy/transfer affected case hearing
   d) Availability of court halls/infrastructure

4. Procedural impediments (if any):
   a) Whether case pendency is due to interlocutory applications
   b) Whether any interim orders are restricting final disposal
   c) Whether appeals/revisions are pending elsewhere
   d) Status of any remittals or relegations

LEGAL BASIS:

The Honorable Supreme Court of India has mandated transparency regarding
judicial administration and case disposal timelines [Ref: Articles 21 &
226, Constitution; Section 4, RTI Act, 2005].

This information is sought in the larger public interest to ensure
accountability in the judicial system.

DECLARATION:

I hereby declare that the information sought will be used for legitimate
purposes relating to understanding judicial administration and ensuring
constitutional compliance.

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

I respectfully request acknowledgment within 5 days and information within
30 days of receipt, as mandated by Section 7, RTI Act, 2005.

Sincerely,

({applicant_name})
"""

    # =========================================================================
    # TEMPLATE 7: DATA DISCREPANCIES
    # =========================================================================
    
    DATA_DISCREPANCIES_TEMPLATE = """
RTI REQUEST FOR CLARIFICATION OF CASE DATA DISCREPANCIES
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Information Regarding Data Inconsistencies
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Under the Right to Information Act, 2005, I hereby request clarification
and corrected information regarding discrepancies I have identified in
official case records.

DETAILS OF DISCREPANCIES IDENTIFIED:

{discrepancy_details}

REQUESTED INFORMATION:

1. Verification of case records:
   a) Certified confirmation of correct case number as per court registry
   b) Correct filing date vs. discrepant date found in public records
   c) Actual case type and jurisdiction vs. listed category
   d) Names of actual parties to the suit

2. Cause of data inconsistencies:
   a) Whether discrepancies arose from data entry errors
   b) Whether case details were amended/corrected post-filing
   c) Whether wrong information was published inadvertently
   d) Timeline of any corrections made to court records

3. Corrected information:
   a) Complete, verified, and accurate case details
   b) Confirmation of whether such discrepancies exist in digital records
   c) Steps taken to correct data in public-facing systems

4. Quality assurance measures:
   a) Whether data verification processes exist in the court
   b) Procedure for correcting published case information
   c) Timeline for updating public portals with corrections

IMPACT:

These data discrepancies have created confusion in tracking case progress
and have affected public understanding. Accurate information is essential
for transparency and public confidence in the judicial system.

DECLARATION:

I declare that I am bringing these discrepancies to the court's attention
with the intention of ensuring data accuracy and strengthening the court's
public information systems.

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

I request acknowledgment within 5 days and corrected information within
30 days of this application's receipt.

Sincerely,

({applicant_name})
"""

    # =========================================================================
    # CUSTOM TEMPLATE (PLACEHOLDER)
    # =========================================================================
    
    CUSTOM_TEMPLATE = """
RTI REQUEST - CUSTOM QUERY
RTI Act, 2005 - Section 3

[DATE]

The Public Information Officer,
{pio_name},
{court_name},
{court_address},
{state},
{pincode}

SUBJECT: RTI Request for Information
         Case No. {case_number}/{case_year}

Respected Sir/Madam,

Pursuant to the Right to Information Act, 2005, I hereby request the
following information:

REQUESTED INFORMATION:

{custom_request}

DECLARATION:

I hereby declare that I am seeking the above information in the public
interest and for legitimate purposes under the RTI Act, 2005.

CONTACT DETAILS:

Name: {applicant_name}
Address: {applicant_address}
Email: {applicant_email}
Phone: {applicant_phone}

I request acknowledgment within 5 days and the information within 30 days
as prescribed by the RTI Act, 2005.

Sincerely,

({applicant_name})
"""

    @classmethod
    def get_template(cls, request_type: RTIRequestType) -> str:
        """Get template by request type."""
        templates = {
            RTIRequestType.MISSING_CASE_RECORDS: cls.MISSING_CASE_RECORDS_TEMPLATE,
            RTIRequestType.TRANSFER_HISTORY: cls.TRANSFER_HISTORY_TEMPLATE,
            RTIRequestType.HEARING_TRANSCRIPTS: cls.HEARING_TRANSCRIPTS_TEMPLATE,
            RTIRequestType.PENDING_ORDERS_STATUS: cls.PENDING_ORDERS_STATUS_TEMPLATE,
            RTIRequestType.CASE_LISTING_DETAILS: cls.CASE_LISTING_DETAILS_TEMPLATE,
            RTIRequestType.ADMINISTRATIVE_DELAYS: cls.ADMINISTRATIVE_DELAYS_TEMPLATE,
            RTIRequestType.DATA_DISCREPANCIES: cls.DATA_DISCREPANCIES_TEMPLATE,
            RTIRequestType.CUSTOM: cls.CUSTOM_TEMPLATE,
        }
        return templates.get(request_type, cls.CUSTOM_TEMPLATE)

    @classmethod
    def list_available_templates(cls) -> List[dict]:
        """List all available RTI request templates with descriptions."""
        return [
            {
                "type": RTIRequestType.MISSING_CASE_RECORDS,
                "title": "Missing Case Records",
                "description": "Request for complete case file, orders, and listing details"
            },
            {
                "type": RTIRequestType.TRANSFER_HISTORY,
                "title": "Case Transfer History",
                "description": "Request for all transfers, remittals, and jurisdictional movements"
            },
            {
                "type": RTIRequestType.HEARING_TRANSCRIPTS,
                "title": "Hearing Transcripts & Recordings",
                "description": "Request for audio recordings and transcripts of court hearings"
            },
            {
                "type": RTIRequestType.PENDING_ORDERS_STATUS,
                "title": "Pending Orders Status",
                "description": "Request for information on orders reserved for judgment"
            },
            {
                "type": RTIRequestType.CASE_LISTING_DETAILS,
                "title": "Case Listing Details",
                "description": "Request for historical cause list and listing pattern information"
            },
            {
                "type": RTIRequestType.ADMINISTRATIVE_DELAYS,
                "title": "Administrative Delays",
                "description": "Request for information on reasons for case disposal delays"
            },
            {
                "type": RTIRequestType.DATA_DISCREPANCIES,
                "title": "Data Discrepancies",
                "description": "Request for clarification of inconsistencies in official records"
            },
            {
                "type": RTIRequestType.CUSTOM,
                "title": "Custom Request",
                "description": "Create a custom RTI request with specific questions"
            },
        ]
