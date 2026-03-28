#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/app')
os.chdir('/app')

#Try to import the app module
try:
    from sqlalchemy import inspect, text
    from app.db.session import engine
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables in database: {tables}")
    
    # Check if alembic_version table exists
    if 'alembic_version' in tables:
        print("✓ alembic_version table exists")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
            versions = [row[0] for row in result]
            print(f"Current migrations: {versions}")
    else:
        print("✗ alembic_version table does not exist - need to run migrations")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
