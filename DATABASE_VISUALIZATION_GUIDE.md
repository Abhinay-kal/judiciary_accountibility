# Database & Architecture Visualization Guide

## Installed Extensions

### ✅ SQL Tools + PostgreSQL Driver
- **Purpose**: Connect to your PostgreSQL database and view schema
- **Status**: Already installed
- **How to use**:
  1. Open Command Palette (Cmd+Shift+P)
  2. Type "SQL Tools: Add New Connection"
  3. Select PostgreSQL
  4. Enter connection details from `alembic.ini`:
     - **Host**: `localhost` or `db` (if using Docker)
     - **Port**: `5432`
     - **Database**: `justice_tracker`
     - **Username**: `postgres`
     - **Password**: `postgres`
  5. Browse tables, views, and schemas in the explorer

### ✅ Markdown Preview Mermaid Support
- **Purpose**: Create architecture diagrams in Markdown
- **Install**: Done ✓
- **How to use**:
  1. Create `.md` file with Mermaid syntax
  2. Use Preview (Cmd+Shift+V) to visualize
  3. Export as image via right-click

### ✅ PlantUML
- **Purpose**: Generate complex architecture diagrams
- **Install**: Done ✓
- **How to use**:
  1. Create `.puml` file
  2. Use PlantUML preview
  3. Export as PNG/SVG

---

## Database Visualization Methods

### Method 1: Using SQL Tools in VSCode (Easiest)
```
1. Connect to PostgreSQL via SQL Tools extension
2. Right-click database → View Tables
3. Visual schema browser built into VSCode
4. Query relationships between tables
```

### Method 2: Generate ER Diagram with Mermaid
Create `DATABASE_ER_DIAGRAM.md`:
```mermaid
erDiagram
    CASES ||--o{ HEARINGS : contains
    CASES ||--o{ JUDGES : assigned_to
    HEARINGS ||--o{ ADJOURNMENTS : has
    CASES ||--o{ RTI_REQUESTS : linked_to
```

### Method 3: Using Docker pgAdmin
Already available in your `docker-compose.yml`:
```bash
docker-compose up
# Visit http://localhost:5050
# Login with default credentials
# Add PostgreSQL server at db:5432
```

### Method 4: DBeaver (Professional Option)
```bash
brew install dbeaver-community

# Then connect to your database for professional ER diagrams
```

---

## Quick Connection Test

Run this to verify database connectivity:
```bash
# From project root with .venv activated
python -c "
from sqlalchemy import create_engine, inspect
engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/justice_tracker')
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Tables found: {tables}')
"
```

---

## Your Project Architecture

### Components
```
┌─────────────────────────────────────────┐
│         Next.js Frontend                │
│  (React + TypeScript + Tailwind)        │
└────────────────┬────────────────────────┘
                 │ /api/v1
┌────────────────▼────────────────────────┐
│       FastAPI Backend                   │
│  (Python + SQLAlchemy + Alembic)        │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│     PostgreSQL Database                 │
│  (Migrations via Alembic)               │
└─────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      Celery Task Queue                  │
│  (Redis/RabbitMQ for async processing)  │
└─────────────────────────────────────────┘
```

### Key Tables (from your codebase)
- `cases` - Main judicial cases
- `hearings` - Case hearings and outcomes
- `adjournments` - Delay tactics classification
- `judges` - Judge information
- `rti_requests` - RTI data
- `corrections` - User corrections/feedback

---

## Recommended Next Steps

1. **Quick Win**: Use SQL Tools extension to explore your schema
2. **Documentation**: Create architecture diagrams in Mermaid format
3. **Professional**: Install DBeaver for advanced ER diagrams
4. **Automation**: Use SchemaCrawler CLI to auto-generate diagrams on schema changes

---

## Troubleshooting

### SQL Tools Connection Failed
- Ensure PostgreSQL is running: `docker-compose ps`
- Check credentials in `alembic.ini`
- Try: `psql -h localhost -U postgres -d justice_tracker`

### Mermaid Preview Not Working
- Reload VSCode window (Cmd+Shift+P → "Developer: Reload Window")
- Ensure file is `.md` format
- Check syntax: https://mermaid.js.org/

---

## Additional Resources

- [SQL Tools Docs](https://vscode-sqltools.mteixeira.dev/)
- [Mermaid Syntax](https://mermaid.js.org/intro/)
- [PlantUML Docs](https://plantuml.com/)
- [pgAdmin Tutorial](https://www.pgadmin.org/docs/)
