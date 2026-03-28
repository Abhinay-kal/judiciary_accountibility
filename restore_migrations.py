#!/usr/bin/env python3
import subprocess
import sys

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
    '0011_hearings_audit_mixin',
    '0012_hearings_audit_mixin_partial',
    '0013_judge_auto_assign',
    '0014_judge_auto_assign_trigger',
    '0015_case_auto_mark_disposed',
    '0016_case_auto_mark_disposed_cleanup',
    '0017_case_disposed_deprecated',
    '0018_dormancy_case_fields',
    '0019_hearing_outcome_hardening',
    '0020_population_runs'
]

for mig in migrations:
    cmd = [
        'docker-compose', 'exec', '-T', 'backend', 'psql',
        '-U', 'postgres', '-d', 'judiciary_accountability',
        '-c', f"INSERT INTO alembic_version (version_num) VALUES ('{mig}') ON CONFLICT DO NOTHING;"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ {mig}")
    else:
        print(f"✗ {mig}: {result.stderr}")
        sys.exit(1)

print("\nAll migrations restored successfully!")
