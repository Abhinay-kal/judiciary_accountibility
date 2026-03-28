"""Case Counsel service for managing counsel assignments to cases."""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import CaseCounsel


class CaseCounselService:
    """Service for managing case counsel assignments."""
    
    @staticmethod
    def assign_counsel(session: Session, case_id: str, advocate_id: int, role: str, 
                      is_lead_counsel: bool = False, notes: Optional[str] = None) -> CaseCounsel:
        """Assign counsel to a case."""
        counsel = CaseCounsel(
            case_id=case_id,
            advocate_id=advocate_id,
            role=role,
            appointment_date=datetime.utcnow(),
            is_lead_counsel=is_lead_counsel,
            notes=notes
        )
        session.add(counsel)
        session.commit()
        session.refresh(counsel)
        return counsel
    
    @staticmethod
    def get_case_counsel(session: Session, counsel_id: int) -> Optional[CaseCounsel]:
        """Get case counsel by ID."""
        return session.query(CaseCounsel).filter(CaseCounsel.id == counsel_id).first()
    
    @staticmethod
    def get_counsel_for_case(session: Session, case_id: str) -> List[CaseCounsel]:
        """Get all counsel assigned to a case."""
        return session.query(CaseCounsel).filter(
            CaseCounsel.case_id == case_id,
            CaseCounsel.removal_date == None
        ).all()
    
    @staticmethod
    def get_cases_for_advocate(session: Session, advocate_id: int) -> List[CaseCounsel]:
        """Get all cases handled by an advocate."""
        return session.query(CaseCounsel).filter(
            CaseCounsel.advocate_id == advocate_id,
            CaseCounsel.removal_date == None
        ).all()
    
    @staticmethod
    def remove_counsel(session: Session, counsel_id: int) -> Optional[CaseCounsel]:
        """Remove counsel from a case."""
        counsel = CaseCounselService.get_case_counsel(session, counsel_id)
        if not counsel:
            return None
        
        counsel.removal_date = datetime.utcnow()
        session.commit()
        session.refresh(counsel)
        return counsel
    
    @staticmethod
    def update_counsel_role(session: Session, counsel_id: int, new_role: str) -> Optional[CaseCounsel]:
        """Update the role of assigned counsel."""
        counsel = CaseCounselService.get_case_counsel(session, counsel_id)
        if not counsel:
            return None
        
        counsel.role = new_role
        session.commit()
        session.refresh(counsel)
        return counsel
    
    @staticmethod
    def set_lead_counsel(session: Session, case_id: str, counsel_id: int) -> bool:
        """Set a counsel as the lead counsel for a case."""
        # Unset other lead counsels for this case
        session.query(CaseCounsel).filter(
            CaseCounsel.case_id == case_id,
            CaseCounsel.is_lead_counsel == True
        ).update({"is_lead_counsel": False})
        
        # Set the new lead counsel
        counsel = CaseCounselService.get_case_counsel(session, counsel_id)
        if counsel and counsel.case_id == case_id:
            counsel.is_lead_counsel = True
            session.commit()
            return True
        
        return False
