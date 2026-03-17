"""
Authority Lookup - PIO (Public Information Officer) Database
RTI Act, 2005

Maintains directory of Public Information Officers across Indian courts,
enabling accurate RTI targeting based on jurisdiction and court level.
"""

from typing import Optional, List, Dict
from dataclasses import dataclass
from .templates import CourtLevel, CourtDetails


@dataclass
class PIOMeta:
    """Public Information Officer metadata and contact details."""
    name: str
    designation: str
    court_level: CourtLevel
    court_name: str
    state: str
    district: Optional[str] = None
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    pincode: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    appeal_authority_name: Optional[str] = None
    appeal_authority_email: Optional[str] = None
    working_hours: str = "09:00 AM - 05:00 PM"
    office_days: str = "Monday to Friday"


class AuthorityLookup:
    """Directory of PIOs across Indian courts."""

    # =========================================================================
    # SUPREME COURT OF INDIA
    # =========================================================================
    
    SUPREME_COURT = PIOMeta(
        name="Public Information Officer",
        designation="PIO - Supreme Court of India",
        court_level=CourtLevel.SUPREME_COURT,
        court_name="Supreme Court of India",
        state="Delhi",
        address_line1="Tilak Marg",
        city="New Delhi",
        pincode="110001",
        email="rtionline.pio@supremecourtofindia.org",
        phone="+91-11-23388922",
        appeal_authority_name="First Appellate Authority - Supreme Court",
        working_hours="09:00 AM - 05:30 PM IST",
        office_days="Monday to Friday",
    )

    # =========================================================================
    # HIGH COURTS - MAJOR STATES
    # =========================================================================
    
    HIGH_COURTS = {
        "delhi": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Delhi High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Delhi",
            state="Delhi",
            district="Delhi",
            address_line1="Rajendra Prasad Road",
            city="New Delhi",
            pincode="110001",
            email="pio.delhi@delhihighcourt.nic.in",
            phone="+91-11-23436373",
            appeal_authority_name="Registrar General - Delhi High Court",
        ),
        "mumbai": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Mumbai High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Bombay",
            state="Maharashtra",
            district="Mumbai",
            address_line1="Shrimandir Road",
            city="Mumbai",
            pincode="400032",
            email="pio@bombayHighcourt.nic.in",
            phone="+91-22-61421111",
            appeal_authority_name="Registrar General - Mumbai High Court",
        ),
        "bangalore": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Karnataka High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Karnataka",
            state="Karnataka",
            district="Bangalore",
            address_line1="Vidhana Soudha",
            city="Bangalore",
            pincode="560001",
            email="pio.rti@karnatakahighcourt.nic.in",
            phone="+91-80-22291000",
            appeal_authority_name="Registrar General - Karnataka High Court",
        ),
        "kolkata": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Calcutta High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Calcutta",
            state="West Bengal",
            district="Kolkata",
            address_line1="1 Esplanade Row East",
            city="Kolkata",
            pincode="700069",
            email="pio.rti@calcuttahighcourt.nic.in",
            phone="+91-33-22143161",
            appeal_authority_name="Registrar General - Calcutta High Court",
        ),
        "madras": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Madras High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Madras",
            state="Tamil Nadu",
            district="Chennai",
            address_line1="Fort St. George Road",
            city="Chennai",
            pincode="600001",
            email="pio@mhc.tn.nic.in",
            phone="+91-44-25338888",
            appeal_authority_name="Registrar General - Madras High Court",
        ),
        "chandigarh": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Punjab & Haryana High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Punjab and Haryana",
            state="Punjab",
            district="Chandigarh",
            address_line1="Sector 17-C",
            city="Chandigarh",
            pincode="160017",
            email="pio.rti@phc.gov.in",
            phone="+91-172-2711100",
            appeal_authority_name="Registrar General - Punjab & Haryana High Court",
        ),
        "ahemedabad": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Gujarat High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Gujarat",
            state="Gujarat",
            district="Ahmedabad",
            address_line1="Akbar Road",
            city="Ahmedabad",
            pincode="380001",
            email="pio.hcguj@gujarathighcourt.nic.in",
            phone="+91-79-27546666",
            appeal_authority_name="Registrar General - Gujarat High Court",
        ),
        "ranchi": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Jharkhand High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Jharkhand",
            state="Jharkhand",
            district="Ranchi",
            address_line1="Court Road",
            city="Ranchi",
            pincode="834001",
            email="pio.rti@jharkhandhighcourt.nic.in",
            phone="+91-651-2413333",
            appeal_authority_name="Registrar General - Jharkhand High Court",
        ),
        "hyderabad": PIOMeta(
            name="Public Information Officer",
            designation="PIO - Telangana High Court",
            court_level=CourtLevel.HIGH_COURT,
            court_name="High Court of Telangana",
            state="Telangana",
            district="Hyderabad",
            address_line1="Hussain Sagar Road",
            city="Hyderabad",
            pincode="500004",
            email="pio.hcts@tshighcourt.nic.in",
            phone="+91-40-66346666",
            appeal_authority_name="Registrar General - Telangana High Court",
        ),
    }

    @classmethod
    def get_pio_by_court(
        cls,
        court_level: CourtLevel,
        state: str,
        district: Optional[str] = None,
    ) -> Optional[PIOMeta]:
        """
        Retrieve PIO details for a specific court.
        
        Args:
            court_level: District/High/Supreme Court
            state: State code or name
            district: District name (for district courts)
            
        Returns:
            PIOMeta object with PIO details, or None if not found
        """
        state_lower = state.lower().strip()

        if court_level == CourtLevel.SUPREME_COURT:
            return cls.SUPREME_COURT

        elif court_level == CourtLevel.HIGH_COURT:
            # Map common state aliases to keys
            state_mapping = {
                "delhi": "delhi",
                "maharashtra": "mumbai",
                "karnataka": "bangalore",
                "west bengal": "kolkata",
                "tamil nadu": "madras",
                "punjab": "chandigarh",
                "haryana": "chandigarh",
                "punjab & haryana": "chandigarh",
                "gujarat": "ahemedabad",
                "jharkhand": "ranchi",
                "telangana": "hyderabad",
            }
            
            key = state_mapping.get(state_lower)
            if key:
                return cls.HIGH_COURTS.get(key)

        elif court_level == CourtLevel.DISTRICT_COURT:
            # District courts - generate generic PIO entry
            return cls._generate_district_court_pio(state, district)

        return None

    @classmethod
    def _generate_district_court_pio(
        cls, state: str, district: Optional[str]
    ) -> PIOMeta:
        """
        Generate PIO entry for district court (generic fallback).
        
        In production, this would query a more complete database.
        """
        district_name = district or state
        return PIOMeta(
            name="Public Information Officer",
            designation=f"PIO - District Court, {district_name}",
            court_level=CourtLevel.DISTRICT_COURT,
            court_name=f"District Court of {district_name}",
            state=state,
            district=district_name,
            address_line1=f"{district_name} Court Building",
            city=district_name,
            pincode="000000",  # Placeholder
            email=f"pio.{district_name.lower().replace(' ', '')}@districtcourt.gov.in",
            phone="+91-NA",
            appeal_authority_name=f"District Judge - {district_name}",
        )

    @classmethod
    def search_by_state(cls, state: str) -> List[PIOMeta]:
        """Search for all PIOs in a given state."""
        state_lower = state.lower().strip()
        results = []

        # Add High Court for state if exists
        if state_lower in cls.HIGH_COURTS:
            results.append(cls.HIGH_COURTS[state_lower])

        return results

    @classmethod
    def get_format_address(cls, pio: PIOMeta) -> str:
        """Format PIO address for RTI request."""
        address_parts = [
            pio.name,
            pio.designation,
        ]
        
        if pio.address_line1:
            address_parts.append(pio.address_line1)
        if pio.address_line2:
            address_parts.append(pio.address_line2)
        
        address_parts.append(f"{pio.city} - {pio.pincode}")
        address_parts.append(pio.state)
        address_parts.append("India")

        return "\n".join(address_parts)

    @classmethod
    def list_all_pios(cls) -> List[Dict]:
        """List all known PIOs in the system."""
        pios = [cls.SUPREME_COURT]
        pios.extend(cls.HIGH_COURTS.values())
        
        return [{
            "name": pio.name,
            "court": pio.court_name,
            "state": pio.state,
            "district": pio.district,
            "level": pio.court_level.value,
            "email": pio.email,
            "phone": pio.phone,
        } for pio in pios]

    @classmethod
    def get_appeal_authority(cls, pio: PIOMeta) -> str:
        """Get First Appellate Authority name for a PIO."""
        return pio.appeal_authority_name or "Court Registry"

    @classmethod
    def get_submission_modes(cls) -> List[Dict]:
        """Get acceptable RTI submission modes as per RTI Rules."""
        return [
            {
                "mode": "offline",
                "method": "Physical submission at court address",
                "description": "Hand-delivered to PIO office during working hours"
            },
            {
                "mode": "online_email",
                "method": "Email to PIO",
                "description": "Send RTI request to provided email with read receipt"
            },
            {
                "mode": "online_portal",
                "method": "Court RTI Portal (if available)",
                "description": "Submit through official court online RTI system"
            },
            {
                "mode": "registered_post",
                "method": "Registered Post with Acknowledgment Due",
                "description": "Recommended for proof of submission date"
            },
            {
                "mode": "speed_post",
                "method": "Speed Post",
                "description": "Faster than registered mail"
            },
        ]
