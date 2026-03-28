"""Interim Applications service for managing interim relief applications."""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import InterimApplication


class InterimApplicationsService:
    """Service for managing interim applications (temporary relief requests)."""
    
    @staticmethod
    def create_application(session: Session, case_id: str, application_type: str,
                          description: str, petitioner_name: str, application_date: datetime,
                          **kwargs) -> InterimApplication:
        """Create a new interim application."""
        app = InterimApplication(
            case_id=case_id,
            application_type=application_type,
            description=description,
            petitioner_name=petitioner_name,
            application_date=application_date,
            **kwargs
        )
        session.add(app)
        session.commit()
        session.refresh(app)
        return app
    
    @staticmethod
    def get_application(session: Session, app_id: int) -> Optional[InterimApplication]:
        """Get interim application by ID."""
        return session.query(InterimApplication).filter(InterimApplication.id == app_id).first()
    
    @staticmethod
    def get_applications_for_case(session: Session, case_id: str, 
                                 status: Optional[str] = None) -> List[InterimApplication]:
        """Get all interim applications for a case."""
        query = session.query(InterimApplication).filter(InterimApplication.case_id == case_id)
        if status:
            query = query.filter(InterimApplication.status == status)
        return query.order_by(InterimApplication.application_date.desc()).all()
    
    @staticmethod
    def get_pending_applications(session: Session, case_id: str) -> List[InterimApplication]:
        """Get pending interim applications for a case."""
        return InterimApplicationsService.get_applications_for_case(session, case_id, status="pending")
    
    @staticmethod
    def approve_application(session: Session, app_id: int, 
                           order_summary: Optional[str] = None) -> Optional[InterimApplication]:
        """Approve an interim application."""
        app = InterimApplicationsService.get_application(session, app_id)
        if not app:
            return None
        
        app.status = "approved"
        app.approval_date = datetime.utcnow()
        if order_summary:
            app.order_summary = order_summary
        
        session.commit()
        session.refresh(app)
        return app
    
    @staticmethod
    def reject_application(session: Session, app_id: int, 
                          order_summary: Optional[str] = None) -> Optional[InterimApplication]:
        """Reject an interim application."""
        app = InterimApplicationsService.get_application(session, app_id)
        if not app:
            return None
        
        app.status = "rejected"
        app.rejection_date = datetime.utcnow()
        if order_summary:
            app.order_summary = order_summary
        
        session.commit()
        session.refresh(app)
        return app
    
    @staticmethod
    def withdraw_application(session: Session, app_id: int) -> Optional[InterimApplication]:
        """Withdraw an interim application."""
        app = InterimApplicationsService.get_application(session, app_id)
        if not app:
            return None
        
        app.status = "withdrawn"
        session.commit()
        session.refresh(app)
        return app
    
    @staticmethod
    def update_application(session: Session, app_id: int, **kwargs) -> Optional[InterimApplication]:
        """Update interim application details."""
        app = InterimApplicationsService.get_application(session, app_id)
        if not app:
            return None
        
        # Don't allow status changes through this method
        kwargs.pop('status', None)
        
        for key, value in kwargs.items():
            if hasattr(app, key):
                setattr(app, key, value)
        
        session.commit()
        session.refresh(app)
        return app
    
    @staticmethod
    def get_applications_by_type(session: Session, application_type: str) -> List[InterimApplication]:
        """Get all interim applications of a specific type."""
        return session.query(InterimApplication).filter(
            InterimApplication.application_type == application_type
        ).order_by(InterimApplication.application_date.desc()).all()
    
    @staticmethod
    def get_applications_by_judge(session: Session, judge_name: str) -> List[InterimApplication]:
        """Get all interim applications handled by a specific judge."""
        return session.query(InterimApplication).filter(
            InterimApplication.judge_name == judge_name
        ).order_by(InterimApplication.application_date.desc()).all()
