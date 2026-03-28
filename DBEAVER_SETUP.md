# DBeaver Setup Guide: Professional ER Diagram Generation (Optional)

## Overview

DBeaver is a professional database GUI tool that provides advanced features beyond SQL Tools:
- Professional ER diagram generation
- Export to PDF/PNG/SVG formats
- Database comparison and synchronization
- Advanced data exploration and reporting
- Schema reverse engineering with customization

**Choice**: Use SQL Tools (included) for quick schema browsing, or DBeaver (optional install) for professional diagrams.

## Installation

### Option A: DBeaver Community Edition (Recommended for this project)

**Free, open-source, full-featured.**

#### On macOS:
```bash
# Using Homebrew (easiest)
brew install dbeaver-community

# Or download directly
# Visit: https://dbeaver.io/download/
# Download macOS .dmg and double-click to install
```

#### On Windows/Linux:
```bash
# Windows: Download .msi from https://dbeaver.io/download/
# Linux: sudo apt-get install dbeaver-community (Debian/Ubuntu)
```

#### Verify Installation:
```bash
which dbeaver  # macOS/Linux
dbeaver --version
```

### Option B: DBeaver Enterprise Edition

**Paid subscription, includes advanced features:**
- Team collaboration
- Advanced data governance
- Extended SQL formatting
- Priority support

For personal projects, Community Edition is sufficient.

## Setup: PostgreSQL Connection

### 1. Launch DBeaver
- macOS: Applications → DBeaver
- Windows/Linux: Start menu → DBeaver
- First time? Accept license, skip setup wizard

### 2. Create New Connection

**Method 1: File Menu**
1. **File** → **New Database Connection**
2. Select **PostgreSQL** → **Next**

**Method 2: Connection Wizard**
1. Click **+ New Connection** button (left sidebar)
2. Choose **PostgreSQL**

### 3. Connection Parameters

Fill in connection details:

| Field | Value |
|-------|-------|
| **Server Host** | `localhost` |
| **Port** | `5432` |
| **Database** | `justice_tracker` |
| **Username** | `postgres` |
| **Password** | `[your-password]` |
| **Save password locally** | ✓ (for convenience) |

### 4. Download PostgreSQL JDBC Driver (if prompted)

DBeaver may ask to download the PostgreSQL JDBC driver.
- Click **Download** → Auto-installs → Done

### 5. Test Connection

Click **Test Connection**:
- ✅ "Connected successfully" → Proceed
- ❌ Error? Check:
  - PostgreSQL running: `pg_isready -h localhost`
  - Firewall blocking 5432
  - Wrong credentials

### 6. Finish & Save

Click **Finish**. Connection appears in **Database Navigator** (left sidebar):

```
Database Navigator
  ├─ Connections
  ├─ PostgreSQL - localhost
  │  ├─ Databases
  │  │  ├─ justice_tracker  ← Your connection
  │  │  │  ├─ Schemas
  │  │  │  │  ├─ public
  │  │  │  │  │  ├─ Tables (60+)
  │  │  │  │  │  ├─ Views
  │  │  │  │  │  ├─ Functions
  │  │  │  │  │  ├─ Triggers
  │  │  │  │  │  └─ Sequences
```

## Generating ER Diagrams

### Method 1: Quick ER Diagram (Entire Schema)

1. Right-click `public` schema → **Diagrams** → **New ER Diagram**
2. DBeaver generates diagram with all tables
3. Preview appears in center editor
4. **Export** → **Save As** → Choose format:
   - PNG (for web/email)
   - PDF (for reports)
   - SVG (for editing)

### Method 2: Filtered ER Diagram (Selected Tables)

For cleaner diagrams, select specific domains:

#### Domain 1: Core Case Management
1. Select tables (Ctrl/Cmd+click):
   - `courts`
   - `judges`
   - `cases`
   - `hearings`
   - `orders`

2. Right-click → **Diagrams** → **New ER Diagram from Selection**
3. Clean diagram with only core entities
4. Save as `architecture_core_er.pdf`

#### Domain 2: Delay Detection
1. Select tables:
   - `cases`
   - `hearings`
   - `adjournments`
   - `case_predictions`
   - `delay_baselines`
   - `survival_curve`

2. Generate diagram → Save as `architecture_delays_er.pdf`

#### Domain 3: Moderation
1. Select tables:
   - `cases`
   - `correction_requests`
   - `moderation_logs`
   - `case_feedback`
   - `content_label`
   - `flag`

2. Generate diagram → Save as `architecture_moderation_er.pdf`

### ER Diagram Features

**Once diagram is open:**

| Feature | How to Use |
|---------|-----------|
| **Zoom** | Scroll wheel / Pinch |
| **Pan** | Click + drag background |
| **Show/Hide labels** | Right-click → Display options |
| **Highlight relationships** | Click table → Related tables highlight |
| **Export** | Right-click canvas → Export as PNG/PDF/SVG |
| **Print** | File → Print (with page setup) |
| **Share** | Copy PNG to clipboard or email PDF |

### Customization

**Before exporting, customize:**

1. **Right-click diagram** → **Edit Diagram**
2. **Display options**:
   - ☑ Show column names
   - ☑ Show column types
   - ☑ Show relationships
   - ☑ Show constraints
3. **Appearance**:
   - Font size
   - Layout direction (top-down vs. left-right)
   - Colors and styles

## Advanced Features (Optional)

### Compare Schemas (Version Control)

Compare your local DB with production:

1. **Tools** → **Database** → **Compare Schemas**
2. Select source (local) and target (production)
3. DBeaver shows differences:
   - New tables/columns
   - Dropped tables
   - Changed constraints
4. Export comparison report

### Data Export

Export entire schema or specific tables:

1. Right-click table → **Export Data**
2. Choose format:
   - CSV (spreadsheet)
   - SQL (INSERT statements)
   - JSON (API-friendly)
   - XML
3. Save to file

### SQL Execution & Debugging

Run and debug SQL queries:

1. **File** → **New SQL Script** (or Ctrl+Alt+N)
2. Write SQL:
```sql
SELECT c.case_number, COUNT(h.id) as hearing_count
FROM cases c
JOIN hearings h ON c.id = h.case_id
GROUP BY c.id
ORDER BY hearing_count DESC
LIMIT 10;
```

3. **Execute** (Ctrl+Enter)
4. Results in bottom panel
5. **Export results** as CSV/JSON/XML

## Integration with VSCode

**Option 1: Keep both open**
- SQL Tools in VSCode for quick queries
- DBeaver for professional diagrams

**Option 2: Open DBeaver from VSCode**
- Or just launch DBeaver separately

## Tips & Best Practices

### Performance with Large Databases
- DBeaver can slow down with 100+ tables
- Use **filtered ER diagrams** (select 5-10 tables at a time)
- Or **hide columns** to simplify view

### Master Diagram (Full Schema Export)

Create one master diagram showing all relationships:

1. Select all tables in justice_tracker
2. Right-click → **Diagrams** → **New ER Diagram**
3. Right-click canvas → **Edit Diagram**
4. **Display options** → Uncheck "Show column names" (to reduce clutter)
5. Export as `master_architecture_er.pdf`

### Documentation

After generating diagrams:

1. **Save PDFs** to `docs/` folder:
   - `docs/architecture_core_er.pdf`
   - `docs/architecture_delays_er.pdf`
   - `docs/architecture_moderation_er.pdf`
   - `docs/master_architecture_er.pdf`

2. **Reference in README**:
```markdown
## Database Architecture

See [core ER diagram](docs/architecture_core_er.pdf) for relationships.

Advanced features in:
- [Delay detection](docs/architecture_delays_er.pdf)
- [Moderation pipeline](docs/architecture_moderation_er.pdf)
```

## Troubleshooting

### DBeaver won't connect
- Check PostgreSQL running: `pg_isready -h localhost`
- Test credentials: `psql -h localhost -U postgres -d justice_tracker`
- Firewall blocking 5432? Add exception
- Driver missing? Let DBeaver download it

### Diagram rendering slow
- Try **Hide columns** option
- Reduce table count (use filtered diagrams)
- Zoom out for better overview

### PDF export quality issues
- Click **Export options**
- Increase DPI: 300 (for print quality)
- Select **Fit to page** for automatic scaling

### Tables not appearing in diagram
- Right-click diagram → **Refresh**
- Or right-click schema → **Refresh**
- Check table visibility settings

## Comparison: SQL Tools vs. DBeaver

| Feature | SQL Tools | DBeaver |
|---------|-----------|---------|
| **Cost** | Free (VSCode extension) | Free (CE) / Paid (Enterprise) |
| **ER Diagrams** | Basic (if available) | Professional, customizable |
| **PDF Export** | ❌ | ✅ |
| **Data Import/Export** | Limited | Advanced |
| **Query Execution** | ✅ | ✅ |
| **Schema Compare** | ❌ | ✅ |
| **IDE Integration** | VSCode only | Standalone |
| **Learning Curve** | Minimal | Moderate |

**Recommendation for this project:**
- Use **SQL Tools** for daily schema browsing (integrated in VSCode)
- Use **DBeaver** for generating professional ER diagrams (one-time or quarterly)

## Completed Steps

1. ✅ SQL Tools connected (see SQL_TOOLS_SETUP.md)
2. ✅ Browse schema visually (see BROWSE_SCHEMA.md)
3. ✅ Created Mermaid diagrams (see docs/ARCHITECTURE_*.md)
4. ✅ DBeaver setup (this file)

**All 4 steps complete!**
