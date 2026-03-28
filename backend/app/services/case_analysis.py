"""
Case analysis service for comprehensive case statistics and analytics.
Provides methods for analyzing case data across multiple dimensions.
"""

from sqlalchemy import func, and_, case as case_expr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.models import Case, Court, Hearing, Judge


class CaseAnalysisService:
    """Service for case statistics and analysis operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_total_case_count(self) -> int:
        """Get total count of cases in the database."""
        return self.db.query(func.count(Case.id)).filter(
            Case.is_deleted.is_(False)
        ).scalar() or 0
    
    def get_case_count_by_court(self) -> List[Dict[str, Any]]:
        """Get case counts grouped by court with court names."""
        results = self.db.query(
            Court.id,
            Court.name,
            func.count(Case.id).label('case_count')
        ).join(
            Case, Case.court_id == Court.id
        ).filter(
            Case.is_deleted.is_(False)
        ).group_by(
            Court.id, Court.name
        ).order_by(
            func.count(Case.id).desc()
        ).all()
        
        return [
            {
                'court_id': r[0],
                'court_name': r[1],
                'case_count': r[2]
            }
            for r in results
        ]
    
    def get_case_count_by_state(self) -> List[Dict[str, Any]]:
        """Get case counts grouped by state."""
        results = self.db.query(
            Court.state_code,
            func.count(Case.id).label('case_count')
        ).join(
            Case, Case.court_id == Court.id
        ).filter(
            Case.is_deleted.is_(False),
            Court.state_code.isnot(None)
        ).group_by(
            Court.state_code
        ).order_by(
            func.count(Case.id).desc()
        ).all()
        
        return [
            {
                'state': r[0],
                'case_count': r[1]
            }
            for r in results
        ]
    
    def get_case_count_by_type(self) -> List[Dict[str, Any]]:
        """Get case counts grouped by case type."""
        results = self.db.query(
            Case.case_type,
            func.count(Case.id).label('case_count')
        ).filter(
            Case.is_deleted.is_(False),
            Case.case_type.isnot(None)
        ).group_by(
            Case.case_type
        ).order_by(
            func.count(Case.id).desc()
        ).all()
        
        return [
            {
                'case_type': r[0],
                'case_count': r[1]
            }
            for r in results
        ]
    
    def get_disposal_status_distribution(self) -> Dict[str, Any]:
        """Get distribution of cases by disposal status."""
        results = self.db.query(
            Case.status,
            func.count(Case.id).label('count')
        ).filter(
            Case.is_deleted.is_(False),
            Case.status.isnot(None)
        ).group_by(
            Case.status
        ).all()
        
        total = sum(r[1] for r in results)
        
        return {
            'by_status': [
                {
                    'status': r[0],
                    'count': r[1],
                    'percentage': round((r[1] / total * 100), 2) if total > 0 else 0
                }
                for r in results
            ],
            'total': total
        }
    
    def get_pending_vs_disposed(self) -> Dict[str, Any]:
        """Get count and percentage of pending vs disposed cases."""
        total = self.db.query(func.count(Case.id)).filter(
            Case.is_deleted.is_(False)
        ).scalar() or 0
        
        disposed = self.db.query(func.count(Case.id)).filter(
            Case.is_deleted.is_(False),
            Case.status == 'disposed'
        ).scalar() or 0
        
        pending = total - disposed
        
        return {
            'total': total,
            'disposed': {
                'count': disposed,
                'percentage': round((disposed / total * 100), 2) if total > 0 else 0
            },
            'pending': {
                'count': pending,
                'percentage': round((pending / total * 100), 2) if total > 0 else 0
            }
        }
    
    def get_cases_by_filing_month(self, months_back: int = 12) -> List[Dict[str, Any]]:
        """Get case count by filing month for the last N months."""
        cutoff_date = datetime.now() - timedelta(days=30 * months_back)
        
        results = self.db.query(
            func.to_char(Case.filing_date, 'YYYY-MM').label('month'),
            func.count(Case.id).label('count')
        ).filter(
            Case.is_deleted.is_(False),
            Case.filing_date >= cutoff_date
        ).group_by(
            func.to_char(Case.filing_date, 'YYYY-MM')
        ).order_by(
            func.to_char(Case.filing_date, 'YYYY-MM')
        ).all()
        
        return [
            {
                'month': r[0],
                'case_count': r[1]
            }
            for r in results
        ]
    
    def get_cases_filed_by_date_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get cases filed within a specific date range."""
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            return {'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}
        
        count = self.db.query(func.count(Case.id)).filter(
            Case.is_deleted.is_(False),
            Case.filing_date >= start,
            Case.filing_date <= end
        ).scalar() or 0
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'case_count': count
        }
    
    def get_case_distribution_court_type(self) -> Dict[str, Any]:
        """Get case distribution across courts and case types (matrix format)."""
        results = self.db.query(
            Court.name,
            Case.case_type,
            func.count(Case.id).label('count')
        ).join(
            Case, Case.court_id == Court.id
        ).filter(
            Case.is_deleted.is_(False),
            Court.name.isnot(None),
            Case.case_type.isnot(None)
        ).group_by(
            Court.name, Case.case_type
        ).all()
        
        # Build matrix structure
        matrix = {}
        for court_name, case_type, count in results:
            if court_name not in matrix:
                matrix[court_name] = {}
            matrix[court_name][case_type] = count
        
        return {
            'distribution': matrix,
            'total_entries': len(results)
        }
    
    def get_case_distribution_state_type(self) -> Dict[str, Any]:
        """Get case distribution across states and case types."""
        results = self.db.query(
            Court.state_code,
            Case.case_type,
            func.count(Case.id).label('count')
        ).join(
            Case, Case.court_id == Court.id
        ).filter(
            Case.is_deleted.is_(False),
            Court.state_code.isnot(None),
            Case.case_type.isnot(None)
        ).group_by(
            Court.state_code, Case.case_type
        ).all()
        
        # Build matrix structure
        matrix = {}
        for state_code, case_type, count in results:
            if state_code not in matrix:
                matrix[state_code] = {}
            matrix[state_code][case_type] = count
        
        return {
            'distribution': matrix,
            'total_entries': len(results)
        }
    
    def get_case_statistics_summary(self) -> Dict[str, Any]:
        """Get comprehensive case statistics summary."""
        total_cases = self.get_total_case_count()
        
        # Get disposal stats
        disposal_stats = self.get_pending_vs_disposed()
        
        # Top court
        courts = self.get_case_count_by_court()
        top_court = courts[0] if courts else None
        
        # Top case type
        case_types = self.get_case_count_by_type()
        top_case_type = case_types[0] if case_types else None
        
        return {
            'total_cases': total_cases,
            'disposal_status': disposal_stats,
            'top_court': top_court,
            'top_case_type': top_case_type,
            'unique_courts': len(courts),
            'unique_case_types': len(case_types)
        }
    
    def get_court_performance_overview(self) -> List[Dict[str, Any]]:
        """Get performance overview for each court (disposal rates, etc)."""
        courts_data = self.get_case_count_by_court()
        results = []
        
        for court_info in courts_data:
            court_id = court_info['court_id']
            
            # Total cases in this court
            total = court_info['case_count']
            
            # Disposed cases in this court
            disposed = self.db.query(func.count(Case.id)).filter(
                Case.is_deleted.is_(False),
                Case.court_id == court_id,
                Case.status == 'disposed'
            ).scalar() or 0
            
            disposal_rate = round((disposed / total * 100), 2) if total > 0 else 0
            
            results.append({
                'court_id': court_id,
                'court_name': court_info['court_name'],
                'total_cases': total,
                'disposed_cases': disposed,
                'pending_cases': total - disposed,
                'disposal_rate': disposal_rate
            })
        
        return sorted(results, key=lambda x: x['disposal_rate'], reverse=True)
    
    def get_cases_trend_12_months(self) -> Dict[str, Any]:
        """Get 12-month trend of cases filed."""
        monthly_data = self.get_cases_by_filing_month(months_back=12)
        
        if not monthly_data:
            return {
                'months': [],
                'data': [],
                'peak_month': None,
                'lowest_month': None,
                'average': 0
            }
        
        case_counts = [m['case_count'] for m in monthly_data]
        peak_month = max(monthly_data, key=lambda x: x['case_count']) if monthly_data else None
        lowest_month = min(monthly_data, key=lambda x: x['case_count']) if monthly_data else None
        average = sum(case_counts) / len(case_counts) if case_counts else 0
        
        return {
            'months': [m['month'] for m in monthly_data],
            'data': case_counts,
            'peak_month': peak_month,
            'lowest_month': lowest_month,
            'average': round(average, 2),
            'total': sum(case_counts)
        }
    
    def get_hearing_outcomes_distribution(self) -> Dict[str, Any]:
        """Get distribution of hearing outcomes."""
        results = self.db.query(
            Hearing.outcome,
            func.count(Hearing.id).label('count')
        ).filter(
            Hearing.is_deleted.is_(False),
            Hearing.outcome.isnot(None)
        ).group_by(
            Hearing.outcome
        ).all()
        
        total = sum(r[1] for r in results)
        
        return {
            'by_outcome': [
                {
                    'outcome': r[0],
                    'count': r[1],
                    'percentage': round((r[1] / total * 100), 2) if total > 0 else 0
                }
                for r in results
            ],
            'total': total
        }
    
    def get_adjournment_rate(self) -> Dict[str, Any]:
        """Get adjournment rate from hearing outcomes."""
        total_hearings = self.db.query(func.count(Hearing.id)).filter(
            Hearing.is_deleted.is_(False)
        ).scalar() or 0
        
        adjourned_hearings = self.db.query(func.count(Hearing.id)).filter(
            Hearing.is_deleted.is_(False),
            Hearing.outcome == 'ADJOURNED'
        ).scalar() or 0
        
        adjournment_rate = round((adjourned_hearings / total_hearings * 100), 2) if total_hearings > 0 else 0
        
        return {
            'total_hearings': total_hearings,
            'adjourned_hearings': adjourned_hearings,
            'adjournment_rate': adjournment_rate
        }
