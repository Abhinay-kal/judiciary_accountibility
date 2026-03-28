# SQL Tools Setup Guide: Connect to PostgreSQL

## Overview
SQL Tools is a lightweight database client VSCode extension that lets you browse PostgreSQL schemas, run queries, and explore table relationships directly in the editor.

## Prerequisites
- ✅ SQL Tools extension installed (`mtxr.sqltools`)
- ✅ PostgreSQL driver installed (`mtxr.sqltools-driver-pg`)
- PostgreSQL running on localhost:5432 (or your target instance)
- Database: `justice_tracker` created

## Setup Steps

### 1. Open Command Palette
Press `Cmd+Shift+P` (`Ctrl+Shift+P` on Windows/Linux) and type:
```
Add New Connection
```

### 2. Select PostgreSQL Driver
Choose **PostgreSQL** from the list of database drivers.

### 3. Enter Connection Details

Fill in the connection form with these values:

| Field | Value | Notes |
|-------|-------|-------|
| **Connection Name** | `Judiciary DB` | Friendly name for this connection |
| **Server Address** | `localhost` | PostgreSQL server hostname |
| **Port** | `5432` | Standard PostgreSQL port |
| **Database** | `justice_tracker` | Target database name |
| **Username** | `postgres` | Default PostgreSQL user (adjust if different) |
| **Password** | `[your-password]` | Your PostgreSQL password |
| **SSL Mode** | `disable` | For local dev; use `require` in production |

### 4. Test Connection
Click **Test Connection** to verify:
- ✅ "Connection successful" indicates working setup
- ❌ Error? Check PostgreSQL is running: `pg_isready -h localhost -U postgres`

### 5. Save Connection
Click **Save Connection**. The connection appears in:
- **SQL Tools** sidebar (left panel)
- **Servers** section under your connection name

## Viewing Connection Details

After connection is saved, in SQL Tools sidebar:

```
Servers
  ├─ Judiciary DB
  │  ├─ Databases
  │  │  ├─ justice_tracker      ← Your target DB
  │  │  └─ postgres             (system DB)
  │  ├─ Functions
  │  └─ Routines
```

## Next Steps: Browse Schema

Once connected:

1. **Expand** `Judiciary DB` → `Databases` → `justice_tracker`
2. **Click** the database to open structure explorer
3. **Navigate** to `Tables` folder to see all tables
4. **Right-click** any table to:
   - View table structure (columns, types, constraints)
   - Show table data
   - Run custom SQL query

## Useful SQL Tools Commands

| Command | Use |
|---------|-----|
| `SQL Tools: Run Query` | Execute ad-hoc SQL |
| `SQL Tools: Show Table Records` | Preview table data (first 100 rows) |
| `SQL Tools: Generate INSERT script` | Export data as SQL |
| `SQL Tools: Describe Table` | Show column definitions |
| `SQL Tools: Edit Records` | Edit table data directly in VSCode |

## Example: Query Cases by Court

1. Press `Cmd+Shift+P` → `SQL Tools: Run Query`
2. Write query:
```sql
SELECT c.case_number, c.status, ct.name as court_name
FROM cases c
JOIN courts ct ON c.court_id = ct.id
LIMIT 10;
```
3. Press `Ctrl+Enter` to execute
4. Results display in bottom panel

## Troubleshooting

### Connection fails: "Refused"
- PostgreSQL not running: `brew services start postgresql` (macOS)
- Wrong port: Verify with `lsof -i :5432 | grep LISTEN`
- Wrong credentials: Double-check username/password

### "Database not found"
- Wrong database name: List with `psql -U postgres -l`
- Database needs migration: Run `alembic upgrade head` from backend folder

### Can't see tables
- Connection loaded but no tables? May need to refresh
- Right-click connection → **Refresh**
- Or restart VSCode

### Slow queries
- SQL Tools defaults to 100 row preview
- For large tables, use explicit `LIMIT` in queries
- Or configure result limit in SQL Tools settings

## Connection File Location

SQL Tools stores connections in:
```
~/.vscode/extensions/mtxr.sqltools-[version]/connections.json
```

No manual editing needed—UI handles all config.

## Multi-Connection Setup (Optional)

Can create multiple connections:
- `Judiciary DB` → Production justice_tracker
- `Judiciary Dev` → Local development instance
- `Backup DB` → Archive or staging database

Each appears as separate server in SQL Tools sidebar.
