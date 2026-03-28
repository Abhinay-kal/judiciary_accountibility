#!/usr/bin/env python3
"""Monitor ingestion run progress and status."""
import sys
import time
from datetime import datetime
from app.db.session import SessionLocal
from app.ingestion.models import PopulationRun, PopulationSourceRun
from app.ingestion.enums import RunStatus

def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"

def monitor_run(run_id: str, interval: int = 5, max_iterations: int = None):
    """
    Monitor a population run in real-time.
    
    Args:
        run_id: The run_id to monitor
        interval: Check interval in seconds
        max_iterations: Maximum number of checks (None = infinite)
    """
    db = SessionLocal()
    iteration = 0
    
    try:
        while True:
            iteration += 1
            if max_iterations and iteration > max_iterations:
                break
            
            # Fetch run details
            run = db.query(PopulationRun).filter(
                PopulationRun.run_id == run_id
            ).first()
            
            if not run:
                print(f"❌ Run '{run_id}' not found")
                return
            
            # Fetch source run statistics
            source_runs = db.query(PopulationSourceRun).filter(
                PopulationSourceRun.population_run_id == run.id
            ).all()
            
            # Count by status
            status_counts = {}
            for source_run in source_runs:
                status = source_run.status.value if hasattr(source_run.status, 'value') else str(source_run.status)
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Clear terminal and print header
            print("\033[2J\033[H", end="")
            print("=" * 80)
            print(f"INGESTION RUN MONITOR: {run_id}")
            print("=" * 80)
            print(f"Started:  {run.created_at.isoformat() if run.created_at else 'N/A'}")
            print(f"Updated:  {run.updated_at.isoformat() if run.updated_at else 'N/A'}")
            
            # Calculate duration and status
            if run.created_at:
                duration = (datetime.utcnow() - run.created_at).total_seconds()
            else:
                duration = 0
            
            print(f"Duration: {format_duration(duration)}")
            print()
            
            # Print statistics
            total = len(source_runs)
            print(f"SOURCES: {total} total")
            print("-" * 80)
            
            for status, count in sorted(status_counts.items()):
                pct = (count / total * 100) if total > 0 else 0
                print(f"  {status:15} {count:3} ({pct:5.1f}%)")
            
            print("-" * 80)
            
            # Print some sample sources by status
            print("\nSAMPLE SOURCES:")
            print("-" * 80)
            
            # Show pending sources
            pending = [sr for sr in source_runs if hasattr(sr.status, 'value') and sr.status.value == 'pending' or str(sr.status) == 'pending']
            if pending:
                print(f"\n⏳ PENDING ({len(pending)}):")
                for sr in pending[:3]:
                    print(f"  • {sr.source_name}")
                if len(pending) > 3:
                    print(f"  ... and {len(pending) - 3} more")
            
            # Show processing sources
            processing = [sr for sr in source_runs if hasattr(sr.status, 'value') and sr.status.value == 'processing' or str(sr.status) == 'processing']
            if processing:
                print(f"\n🔄 PROCESSING ({len(processing)}):")
                for sr in processing[:3]:
                    elapsed = ""
                    if sr.started_at:
                        delta = (datetime.utcnow() - sr.started_at).total_seconds()
                        elapsed = f" [{format_duration(delta)}]"
                    print(f"  • {sr.source_name}{elapsed}")
                if len(processing) > 3:
                    print(f"  ... and {len(processing) - 3} more")
            
            # Show completed sources
            completed = [sr for sr in source_runs if hasattr(sr.status, 'value') and sr.status.value == 'completed' or str(sr.status) == 'completed']
            if completed:
                print(f"\n✅ COMPLETED ({len(completed)}):")
                for sr in completed[:3]:
                    print(f"  • {sr.source_name}")
                if len(completed) > 3:
                    print(f"  ... and {len(completed) - 3} more")
            
            # Show failed sources
            failed = [sr for sr in source_runs if hasattr(sr.status, 'value') and sr.status.value == 'failed' or str(sr.status) == 'failed']
            if failed:
                print(f"\n❌ FAILED ({len(failed)}):")
                for sr in failed[:3]:
                    msg = sr.error_message[:40] + "..." if sr.error_message and len(sr.error_message) > 40 else sr.error_message
                    print(f"  • {sr.source_name}: {msg}")
                if len(failed) > 3:
                    print(f"  ... and {len(failed) - 3} more")
            
            print("\n" + "=" * 80)
            
            # Check if run is complete
            if not any(sr for sr in source_runs if hasattr(sr.status, 'value') and sr.status.value in ['pending', 'processing'] or str(sr.status) in ['pending', 'processing']):
                print("✅ RUN COMPLETE")
                break
            
            print(f"(Press Ctrl+C to stop monitoring)")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking again in {interval}s...")
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: monitor_ingestion.py <run_id> [interval] [max_iterations]")
        print("Example: monitor_ingestion.py 20260328-manual-fresh 5 120")
        sys.exit(1)
    
    run_id = sys.argv[1]
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    max_iterations = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    monitor_run(run_id, interval, max_iterations)
