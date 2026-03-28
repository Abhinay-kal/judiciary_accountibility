# Browse Database Tables & Schemas Visually

## Quick Start (2 minutes)

After SQL Tools connection is established:

1. **Open SQL Tools sidebar** — Click database icon in left panel
2. **Expand** `Judiciary DB` → `Databases` → `justice_tracker`
3. **Click** `Tables` folder to list all tables
4. **Click** any table to preview structure
5. **Right-click** → `Show Table Records` to see data

## Understanding Table Structure

When you click a table in SQL Tools, you see:

```
Table: cases
├─ Columns
│  ├─ id (integer, PK)
│  ├─ case_uid (string) ← Unique identifier
│  ├─ case_number (string)
│  ├─ court_id (integer, FK) → courts.id
│  ├─ status (string)
│  ├─ filing_date (date)
│  ├─ created_at (timestamp)
│  └─ [15 more columns...]
├─ Indexes
│  ├─ cases_pkey (Primary key on id)
│  └─ uq_case_number_court
└─ Foreign Keys
   ├─ cases.court_id → courts.id
   └─ [relationships to other tables]
```

**Key Symbols:**
- 🔑 **PK** = Primary Key (unique identifier for each row)
- 🔗 **FK** = Foreign Key (reference to another table)
- ⚡ **idx** = Index (speeds up queries)

## Key Tables & Relationships

### Core Domain (Cases & Courts)

```
courts (central registry)
  ├─ judges (assigned to courts)
  ├─ cases (filed in courts)
└─ orders (case outcomes)

cases (central entity)
  ├─ hearings (proceedings)
  ├─ adjournments (delays)
  ├─ case_predictions (ML predictions)
  └─ case_feedback (citizen contributions)
```

### Delay Detection

```
adjournments
  ├─ case_id → cases
  ├─ hearing_id → hearings
  └─ reason_category (e.g., "adjournment_by_defendant")
```

### Moderation & Quality

```
correction_requests
  ├─ case_id → cases
  ├─ correction_type (e.g., "judge_name", "dates")
  └─ status (pending/approved/rejected)

moderation_logs
  ├─ target_id (case/hearing/judge)
  ├─ action_type (flag/remove/review)
  └─ moderator activity audit trail
```

## Common Queries to Try

### Navigate to all tables from a court
```sql
SELECT ct.name, c.case_number, h.date, h.outcome_text
FROM courts ct
JOIN cases c ON ct.id = c.court_id
LEFT JOIN hearings h ON c.id = h.case_id
WHERE ct.name = 'Delhi High Court'
ORDER BY h.date DESC;
```

### Find delayed cases
```sql
SELECT c.case_number, COUNT(a.id) as adjournment_count
FROM cases c
JOIN adjournments a ON c.id = a.case_id
WHERE a.is_adjournment = true
GROUP BY c.id
HAVING COUNT(a.id) > 5
ORDER BY adjournment_count DESC;
```

### Check moderation activity
```sql
SELECT ml.target_id, ml.action_type, COUNT(*) as count
FROM moderation_logs ml
WHERE ml.created_at > NOW() - INTERVAL '7 days'
GROUP BY ml.target_id, ml.action_type;
```

## Exploring Relationships

### Method 1: Visual in SQL Tools
1. Right-click table → **Show ER Diagram** (if extension supports)
2. Or use **Describe Table** to see all foreign keys

### Method 2: SQL Query
```sql
-- Find all foreign keys for 'cases' table
SELECT 
  tc.constraint_name,
  t.table_name,
  c.column_name,
  ccu.table_name AS foreign_table_name,
  ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND t.table_name = 'cases';
```

## Table Size & Performance

Check which tables are largest:
```sql
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Viewing Indexes

Understand query optimization:
```sql
SELECT 
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY tablename;
```

## Exporting Schema

### Export as SQL DDL
1. Right-click table → **Generate CREATE TABLE script**
2. Or use `pg_dump` command:
```bash
pg_dump -h localhost -U postgres -d justice_tracker --schema-only > schema.sql
```

### Export as CSV (for analysis)
In SQL Tools:
1. Run query
2. Right-click results → **Export** → **CSV**

## Performance Tips

1. **Use LIMIT** for large tables (defaults to 100 rows)
```sql
SELECT * FROM case_feedback LIMIT 100;  -- ~5ms
```

2. **Check indexes** before filtering
```sql
CREATE INDEX idx_cases_status ON cases(status);
SELECT * FROM cases WHERE status = 'pending';  -- Fast
```

3. **Avoid full table scans** on production tables
```sql
-- ❌ Slow: Scans entire 'cases' table
SELECT COUNT(*) FROM cases WHERE case_number LIKE '%2024%';

-- ✅ Fast: Uses exact match
SELECT COUNT(*) FROM cases WHERE case_number = 'CR-2024-001234';
```

## Next Steps

1. ✅ Browse each table structure
2. ✅ Run example queries
3. ✅ Map out relationships
4. Continue to **Architecture Diagrams** (see docs folder)
