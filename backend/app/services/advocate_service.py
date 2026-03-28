"""Advocate service for managing advocate records."""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Advocate


class AdvocateService:
    """Service for managing advocate records."""
    
    @staticmethod
    def create_advocate(session: Session, name: str, registration_number: str, **kwargs) -> Advocate:
        """Create a new advocate record."""
        advocate = Advocate(
            name=name,
            registration_number=registration_number,
            **kwargs
        )
        session.add(advocate)
        session.commit()
        session.refresh(advocate)
        return advocate
    
    @staticmethod
    def get_advocate(session: Session, advocate_id: int) -> Optional[Advocate]:
        """Get an advocate by ID."""
        return session.query(Advocate).filter(Advocate.id == advocate_id).first()
    
    @staticmethod
    def get_advocates_by_registration(session: Session, registration_number: str) -> Optional[Advocate]:
        """Get an advocate by registration number."""
        return session.query(Advocate).filter(
            Advocate.registration_number == registration_number
        ).first()
    
    @staticmethod
    def list_advocates(session: Session, is_active: bool = True, limit: int = 100) -> List[Advocate]:
        """List advocates with optional filtering."""
        query = session.query(Advocate)
        if is_active:
            query = query.filter(Advocate.is_active == True)
        return query.limit(limit).all()
    
    @staticmethod
    def update_advocate(session: Session, advocate_id: int, **kwargs) -> Optional[Advocate]:
        """Update an advocate record."""
        advocate = AdvocateService.get_advocate(session, advocate_id)
        if not advocate:
            return None
        
        for key, value in kwargs.items():
            if hasattr(advocate, key):
                setattr(advocate, key, value)
        
        session.commit()
        session.refresh(advocate)
        return advocate
    
    @staticmethod
    def deactivate_advocate(session: Session, advocate_id: int) -> Optional[Advocate]:
        """Deactivate an advocate."""
        return AdvocateService.update_advocate(session, advocate_id, is_active=False)
