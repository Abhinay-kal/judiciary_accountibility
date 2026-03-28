#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/app')
os.chdir('/app')

try:
    from sqlalchemy import text
    from app.db.session import engine
    
    # All migrations from 0001 to 0022
    migrations = [
        '0001_initial',
        '0002_scale_indexes',
        '0003_ml_predictions',
        '0004_ingestion_resilience',
        '0005_hearing_outcomes',
        '0006_judge_attribution',
        '0007_resilient_ingestion_cas',
        '0008_case_importance_scoring',
        '0009_delay_baseline_analytics',
        '0010_survival_analysis_curves',
        '0011_defamation_safety_layer',
        '0012_right_to_respond_feedback',
        '0013_investigation_snapshots',
        '0014_plain_english_summary_fields',
        '0015_persuasion_impact_fields',
        '0016_field_level_provenance',
        '0017_multi_tier_cache_l3_tables',
        '0018_dormancy_case_fields',
        '0019_hearing_outcome_hardening',
        '0020_population_runs',
        '0021_advocate_entity_model',
        '0022_advocate_materialized_views'
    ]
    
    with engine.begin() as conn:
        for mig in migrations:
            # Check if already exists
            result = conn.execute(text(f"SELECT 1 FROM alembic_version WHERE version_num = :ver"), {"ver": mig})
            if not result.scalar():
                conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:ver)"), {"ver": mig})
                print(f"✓ Recorded {mig}")
            else:
                print(f"- {mig} (already recorded)")
    
    print("\nMigration history successfully restored!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
