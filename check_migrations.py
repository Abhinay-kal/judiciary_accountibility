#!/usr/bin/env python3
"""Check Alembic migration status and fix issues."""

import os
import sys
from sqlalchemy import create_engine, text

# Use the same DATABASE_URL as docker-compose
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:55433/judiciary_accountability"
)

print(f"Connecting to: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    
    # Check if database and alembic_version table exist
    with engine.connect() as conn:
        # Try to query alembic_version
        try:
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
            versions = [row[0] for row in result]
            print(f"✓ Database has {len(versions)} migrations recorded")
            print("Last 5 migrations:")
            for v in versions[-5:]:
                print(f"  - {v}")
        except Exception as e:
            print(f"⚠ Could not query alembic_version: {e}")
            print("This may be the first run or the table doesn't exist")
            
        # List all tables
        try:
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            print(f"\n✓ Database has {len(tables)} tables:")
            for t in tables[:10]:
                print(f"  - {t}")
            if len(tables) > 10:
                print(f"  ... and {len(tables) - 10} more")
        except Exception as e:
            print(f"⚠ Could not list tables: {e}")

    # Now check Alembic configuation
    sys.path.insert(0, "/Users/abhinaykalkhanday/Desktop/judiciary_accountibility/backend")
    
    from alembic import script, config
    
    cfg = config.Config("/Users/abhinaykalkhanday/Desktop/judiciary_accountibility/backend/alembic.ini")
    script_dir = script.ScriptDirectory.from_config(cfg)
    
    try:
        heads = list(script_dir.get_heads())
        print(f"\n✓ Alembic heads: {heads}")
        
        if len(heads) > 1:
            print("⚠ WARNING: Multiple branch heads detected! This causes the 'overlaps' error.")
            print("The migrations have diverged into multiple branches.")
    except Exception as e:
        print(f"⚠ Could not get heads: {e}")
    
    print("\n✓ Migration check complete")
    
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
