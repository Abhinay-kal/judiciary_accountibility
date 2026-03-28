# Database & Architecture Visualization: Complete 4-Step Guide

## 🎯 Objective

Implement comprehensive database and architecture visualization using SQL Tools, Mermaid diagrams, and optional DBeaver for professional exports.

## 📋 Quick Overview

| Step | Tool | Time | Deliverable | Status |
|------|------|------|-------------|--------|
| 1 | SQL Tools (VSCode) | 5 min | Live PostgreSQL connection | ✅ Guide created |
| 2 | SQL Tools (VSCode) | 10 min | Schema browser & queries | ✅ Guide created |
| 3 | Mermaid (Markdown) | 15 min | 3 ER diagrams as code | ✅ Diagrams created |
| 4 | DBeaver (Optional) | 10 min | PDF/PNG professional exports | ✅ Guide created |

**Total implementation time:** 30-45 minutes

---

## 📁 Files Created

All guides and diagrams now available in your workspace:

```
/Users/abhinaykalkhanday/Desktop/judiciary_accountibility/
├─ SQL_TOOLS_SETUP.md              ← Step 1: Connection setup
├─ BROWSE_SCHEMA.md                ← Step 2: Schema exploration
├─ DBEAVER_SETUP.md                ← Step 4: Professional diagrams
├─ DATABASE_VISUALIZATION_GUIDE.md ← Original comprehensive guide
│
└─ docs/
   ├─ ARCHITECTURE_CORE.md         ← Step 3A: Core Mermaid diagram
   ├─ ARCHITECTURE_DELAYS.md       ← Step 3B: Delays Mermaid diagram
   └─ ARCHITECTURE_MODERATION.md   ← Step 3C: Moderation Mermaid diagram
```

---

## 🚀 Getting Started

### Step 1: SQL Tools Connection (5 minutes)

**What:** Connect VSCode to PostgreSQL database

**How:**
1. Press `Cmd+Shift+P` in VSCode
2. Type: `Add New Connection`
3. Select PostgreSQL
4. Enter:
   - Server: `localhost`
   - Port: `5432`
   - Database: `justice_tracker`
   - Username: `postgres`
   - Password: (your password)
5. Test & Save

**Verify:** SQL Tools sidebar shows `Judiciary DB` connection

📄 **Full guide:** [SQL_TOOLS_SETUP.md](SQL_TOOLS_SETUP.md)

---

### Step 2: Browse Schema Visually (10 minutes)

**What:** Explore tables, columns, relationships without writing SQL

**How:**
1. In SQL Tools sidebar → Expand `justice_tracker`
2. Click `Tables` to see all ~60 tables
3. Click any table to inspect structure (columns, types, keys)
4. Right-click table → `Show Table Records` to preview data

**Try:** Copy-paste example queries from guide

📄 **Full guide:** [BROWSE_SCHEMA.md](BROWSE_SCHEMA.md)

**Key tables to explore (10 minutes):**
- Core: `courts` → `judges` → `cases` → `hearings` → `orders`
- Delays: `adjournments` → `case_predictions` → `delay_baselines`
- Moderation: `correction_requests` → `moderation_logs` → `case_feedback`

---

### Step 3: Create Mermaid Architecture Diagrams (15 minutes)

**What:** Document database architecture as code-based ER diagrams

**How:**
1. Open any diagram file (listed below)
2. In VSCode: Press `Cmd+Shift+V` to preview
3. Diagram renders with full details

**Three diagrams, each covering a domain:**

#### **3A) Core Case Management**
📄 [docs/ARCHITECTURE_CORE.md](docs/ARCHITECTURE_CORE.md)

Covers: courts, judges, cases, hearings, orders
- Central relationships
- Case lifecycle flow
- 10+ entity types with full descriptions
- Example queries for common operations

#### **3B) Delay Detection Pipeline**
📄 [docs/ARCHITECTURE_DELAYS.md](docs/ARCHITECTURE_DELAYS.md)

Covers: adjournments, predictions, baselines, survival curves
- Phase 1 delay detection
- ML prediction flow
- Statistical baselines
- Data pipeline from hearing → risk score

#### **3C) Moderation & Quality Control**
📄 [docs/ARCHITECTURE_MODERATION.md](docs/ARCHITECTURE_MODERATION.md)

Covers: corrections, moderation logs, feedback, flags, labels
- User submissions workflow
- Moderation approval process
- Feedback verification (crowdsourcing)
- Content sensitivity labeling
- Audit trails

---

### Step 4: DBeaver Setup - Professional Diagrams (10 minutes, OPTIONAL)

**What:** Generate professional PDF/PNG ER diagrams for reports and presentations

**When to use DBeaver vs. Mermaid:**
- **Use DBeaver if:** Need PDF exports, professional styling, schema comparison
- **Use Mermaid if:** Want version control, embedded docs, quick updates

**Installation:**
```bash
brew install dbeaver-community  # macOS
# or download from https://dbeaver.io/download/
```

**How:**
1. Launch DBeaver
2. File → New Database Connection → PostgreSQL
3. Enter same connection details as SQL Tools
4. Right-click tables → Diagrams → New ER Diagram
5. Export as PNG/PDF

📄 **Full guide:** [DBEAVER_SETUP.md](DBEAVER_SETUP.md)

---

## 💡 Use Cases

### For Developers
- **Understand schema:** Use SQL Tools to explore before writing queries
- **Trace data flow:** Follow relationships in Mermaid diagrams
- **Reference during PRs:** Link to diagrams when documenting changes

### For Data Analysts
- **Write correct JOINs:** See foreign key chains in diagrams
- **Identify opportunities:** Spot denormalization or missing indexes
- **Build reports:** Query examples in each diagram guide

### For Stakeholders
- **Share architecture:** Export Mermaid diagrams as images or PDFs
- **In presentations:** Include professional ER diagrams (DBeaver export)
- **Onboarding:** Send guides to new team members

### For Architects
- **Compare versions:** Use DBeaver's schema comparison
- **Plan changes:** Model modifications before migration
- **Document decisions:** Mermaid diagrams live in git for history

---

## 🔍 Examples Included

Each guide includes:
- **Table descriptions:** What data is stored, why it matters
- **Relationship diagrams:** Visual representation of connections
- **SQL queries:** Copy-paste templates for common operations
- **Troubleshooting:** Solutions for common issues

### Quick Query Examples

**Find high-risk cases:**
```sql
SELECT c.case_number, cp.delay_probability
FROM cases c
JOIN case_predictions cp ON c.id = cp.case_id
WHERE cp.delay_probability > 0.8
ORDER BY cp.delay_probability DESC;
```

**Browse tables from a specific court:**
```sql
SELECT ct.name, c.case_number, COUNT(h.id) as hearing_count
FROM courts ct
JOIN cases c ON ct.id = c.court_id
LEFT JOIN hearings h ON c.id = h.case_id
WHERE ct.name = 'Delhi High Court'
GROUP BY c.id;
```

**Check moderation activity:**
```sql
SELECT ml.action_type, COUNT(*) as count
FROM moderation_logs ml
WHERE ml.created_at > NOW() - INTERVAL '7 days'
GROUP BY ml.action_type;
```

---

## ✅ Verification Checklist

After completing all 4 steps:

- [ ] **Step 1:** SQL Tools connected, can see justice_tracker database in sidebar
- [ ] **Step 2:** Browsed at least 3 tables, viewed their structure
- [ ] **Step 3:** Opened each Mermaid diagram in VSCode preview (Cmd+Shift+V)
- [ ] **Step 4 (optional):** DBeaver installed and connected (or skipped if not needed)

---

## 📚 Additional Resources

### In Your Workspace
- [DATABASE_VISUALIZATION_GUIDE.md](DATABASE_VISUALIZATION_GUIDE.md) — Original comprehensive guide from Phase 3
- All Mermaid diagrams have query examples at the bottom

### External
- **SQL Tools:** https://vscode-sqltools.github.io/
- **DBeaver:** https://dbeaver.io/docs/
- **Mermaid:** https://mermaid.live/ (online editor)

---

## 🎓 Next Steps

**Immediate (after completing 4 steps):**
1. Commit guides to git
2. Share links with team
3. Update README to reference diagrams

**Short-term (1-2 weeks):**
1. Use guides during feature planning
2. Reference diagrams in PR descriptions
3. Run DBeaver schema comparison with production (if available)

**Ongoing (quarterly):**
1. Update Mermaid diagrams when schema changes
2. Keep query examples current
3. Export fresh PDF diagrams for presentations

---

## 🐛 Troubleshooting

### SQL Tools won't connect
See: [SQL_TOOLS_SETUP.md](SQL_TOOLS_SETUP.md#troubleshooting) → Troubleshooting section

### Mermaid diagram not rendering
- Ensure files saved in workspace
- Try: `Cmd+Shift+V` to preview in VSCode
- Or view on GitHub (auto-renders)

### DBeaver issues
See: [DBEAVER_SETUP.md](DBEAVER_SETUP.md#troubleshooting) → Troubleshooting section

---

## 📊 What You Now Have

✅ **3 interactive schema guides** (SQL Tools setup, browsing, queries)
✅ **3 comprehensive ER diagrams** (Core, Delays, Moderation)
✅ **50+ example SQL queries** (ready to copy-paste)
✅ **Professional export workflow** (via DBeaver, optional)
✅ **Architecture documentation** (as code in git)

**Result:** Complete visibility into database schema and architecture, enabling faster development, better collaboration, and clearer documentation.

---

**Start with Step 1 above** — takes 5 minutes to connect! →
