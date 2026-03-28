# Phase 2: Feature Engineering - Deliberate Delay Detection

## Overview

Phase 2 implements quantitative feature engineering on top of Phase 1's adjournment intent classification. While Phase 1 identifies *what* delay tactics are used, Phase 2 quantifies *how much* parties are exploiting those tactics and detects systemic patterns of deliberate delay.

The system extracts four primary features from case hearing histories:
1. **Adjournment Density** - Percentage of hearings that adjourn
2. **Party-Driven Delay Score** - Composite score (0-100) of party involvement in delays
3. **Dormancy Variance** - Statistical analysis of gaps between hearings
4. **Bench Hunting Index** - Judge/bench change frequency and patterns

---

## Module Structure

**Location:** `backend/app/services/delay_detection_phase2.py`

**Dependencies:**
- Phase 1: `app.services.adjournment` (AdjournmentTacticClassifier, DelayTactic)
- ORM: `app.models` (Case, Hearing, HearingOutcomeType)
- SQLAlchemy: Query optimization with indexed lookups

---

## Feature Definitions

### 1. Adjournment Density

**What it measures:** Concentration of adjournments in a case's hearing history.

**Definition:**
$$\text{Density} = \frac{\text{Adjourned Hearings}}{\text{Total Hearings}} \times 100\%$$

**Attributes:**
- `total_hearings: int` - Total substantive + adjourned hearings
- `adjournment_count: int` - Number of adjourned hearings
- `density: float` - Percentage (0-100)
- `trend: str` - Temporal trend ('increasing', 'decreasing', 'stable', 'insufficient_data')
- `recent_density: float` - Adjournment percentage in last 180 days

**Trend Calculation:**
The case hearing history is divided into two equal time periods. Trend is determined by comparing adjournment rates:

| Condition | Trend |
|-----------|-------|
| Second half density > First half + 15% | `increasing` |
| First half density > Second half + 15% | `decreasing` |
| Difference ≤ 15% | `stable` |
| < 3 total hearings | `insufficient_data` |

**Interpretation:**
- **0-20% density**: Normal systemic delays
- **20-40% density**: Elevated delay pattern
- **40%+ density**: Strong indicator of deliberate delays
- **Increasing trend**: Escalating strategic use of adjournments

**Example:**
```python
case = db.query(Case).get(123)
density = FeatureEngineer.compute_adjournment_density(case, db)
# AdjournmentDensity(
#     total_hearings=45,
#     adjournment_count=18,
#     density=40.0,
#     trend='increasing',
#     recent_density=52.3
# )
```

---

### 2. Party-Driven Delay Score

**What it measures:** Estimated probability (0-100) that parties are deliberately causing delays through specific tactics.

**Composition:**
The score combines four factors:

1. **Proxy Counsel Component** (0-40 points)
$$\text{Proxy Score} = \frac{\text{Proxy Counsel Adjournments}}{\text{Total Adjournments}} \times 40$$

2. **Frivolous Filing Component** (0-30 points)
$$\text{Frivolous Score} = \frac{\text{Frivolous Filing Adjournments}}{\text{Total Adjournments}} \times 30$$

3. **Tactic Diversity Bonus** (0-15 points)
$$\text{Diversity Bonus} = \frac{\text{Number of Distinct Tactics}}{4} \times 15$$

4. **Density Factor** (0-15 points)
$$\text{Density Factor} = \min\left(\frac{\text{Adjournment Density}}{100} \times 15, 15\right)$$

**Recurrence Multiplier** (1.0-1.5x):
$$\text{Multiplier} = 1.0 + 0.5 \times \frac{\text{Most Frequent Tactic Count}}{\text{Total Adjournments}}$$

**Final Score:**
$$\text{Score} = \min(100, \max(0, (P + F + D + A) \times M))$$

**Attributes:**
- `score: float` - Final composite score (0-100)
- `proxy_counsel_ratio: float` - Proportion of proxy counsel tactics
- `frivolous_filing_ratio: float` - Proportion of filing defect tactics
- `tactic_diversity: int` - Number of distinct tactic types used (0-4)
- `recurrence_factor: float` - Indicator of repeated use of same tactic
- `explanation: str` - Detailed breakdown of score composition

**Score Interpretation:**
- **0-20**: Low evidence of party-driven delays
- **20-40**: Moderate concern about tactical delays
- **40-60**: Strong evidence of deliberate delay tactics
- **60-80**: Very high concern about coordinated delay tactics
- **80-100**: Extreme likelihood of systematic party-driven delays

**Example:**
```python
score = FeatureEngineer.compute_party_driven_delay_score(case, db)
# PartyDrivenDelayScore(
#     score=72.5,
#     proxy_counsel_ratio=0.444,
#     frivolous_filing_ratio=0.222,
#     tactic_diversity=3,
#     recurrence_factor=0.444,
#     explanation="Party-driven delay score: 72.5/100. Proxy counsel..."
# )
```

---

### 3. Dormancy Variance

**What it measures:** Statistical variability in time gaps between consecutive hearings.

**Rationale:**
- **Low variance** → Consistent systemic scheduling → Delays are institutional
- **High variance with long gaps** → Tactical manipulation → Parties deliberate causing gaps

**Metrics:**

| Metric | Definition | Use |
|--------|-----------|-----|
| `mean_days_between_hearings` | Average gap between consecutive hearings | Baseline for comparison |
| `variance` | Variance of gap lengths (days²) | Raw statistical dispersion |
| `std_dev` | Standard deviation of gaps (days) | Interpretable spread |
| `coefficient_of_variation` | $\frac{\sigma}{\mu}$ normalized spread | Scale-independent measure |
| `max_gap_days` | Longest single gap | Extreme delay indicator |
| `min_gap_days` | Shortest single gap | Efficiency baseline |

**Pattern Classification:**

| Pattern | Definition | Indicators |
|---------|-----------|-----------|
| `consistent` | CV < 0.3 | Regular scheduling, systemic delays |
| `irregular` | 0.3 ≤ CV ≤ 0.8 | Variable scheduling, mixed factors |
| `prolonged_gaps` | CV > 0.8 AND max_gap > 2.5×mean | Tactical long delays with normal hearings |
| `accelerating` | Second-half mean < 0.7×first-half mean | Case resolution accelerating over time |
| `insufficient_data` | < 3 hearings | Cannot classify pattern |

**Example:**
```python
variance = FeatureEngineer.compute_dormancy_variance(case, db)
# DormancyVariance(
#     mean_days_between_hearings=45.2,
#     variance=312.4,
#     std_dev=17.7,
#     max_gap_days=95,
#     min_gap_days=12,
#     coefficient_of_variation=0.392,
#     pattern_type='irregular'
# )
```

---

### 4. Bench Hunting Index

**What it measures:** Frequency and pattern of judge/bench changes, suggesting parties are shopping for favorable judges.

**Bench Hunting Definition:**
Parties strategically cause adjournments or file new applications to change assigned judges, hoping for more favorable rulings.

**Metrics:**

| Metric | Definition | Calculation |
|--------|-----------|------------|
| `judge_change_count` | Number of judge transitions | Δ in judge_id sequence |
| `average_hearings_per_judge` | Mean hearings per judge | Total hearings / unique judges |
| `bench_change_frequency` | Changes per year | Changes / case duration (years) |
| `high_adjournment_judges` | Judges with >50% adjournment rate | Count where adj/total > 0.5 |
| `pattern_strength` | Composite indicator (0-1) | Weighted combination |

**Pattern Strength Calculation:**
$$\text{Strength} = 0.4 \times f + 0.35 \times u + 0.25 \times h$$

Where:
- $f = \min(\text{change frequency} / 2, 1.0)$ - Frequency factor
- $u = \min(\text{unique judges} / \text{total hearings}, 0.5)$ - Uniqueness factor
- $h = \text{high adjournment judges} / \text{unique judges}$ - High-adj factor

**Attributes:**
- `judge_change_count: int` - Number of judge transitions
- `average_hearings_per_judge: float` - Mean hearings per judge
- `bench_change_frequency: float` - Changes per year
- `high_adjournment_judges: int` - Judges with elevated adjournment rates
- `pattern_strength: float` - Confidence (0-1) in bench hunting behavior
- `explanation: str` - Pattern description

**Pattern Interpretation:**
- **Strength 0.0-0.2**: No evidence of bench hunting
- **Strength 0.2-0.4**: Possible bench hunting (watch closely)
- **Strength 0.4-0.6**: Moderate evidence of bench hunting
- **Strength 0.6-0.8**: Strong evidence of bench hunting
- **Strength 0.8-1.0**: Extreme bench hunting pattern

**Example:**
```python
index = FeatureEngineer.compute_bench_hunting_index(case, db)
# BenchHuntingIndex(
#     judge_change_count=8,
#     average_hearings_per_judge=2.25,
#     bench_change_frequency=1.5,  # Per year
#     high_adjournment_judges=3,
#     pattern_strength=0.67,
#     explanation="Bench hunting analysis: 8 judge changes..."
# )
```

---

## API Reference

### FeatureEngineer Class

Main interface for computing Phase 2 features.

#### compute_adjournment_density()

```python
@classmethod
def compute_adjournment_density(
    case: Case,
    db: Session
) -> AdjournmentDensity:
    """Compute adjournment density and trend for a case."""
```

**Parameters:**
- `case: Case` - Case entity from ORM
- `db: Session` - SQLAlchemy session for queries

**Returns:** `AdjournmentDensity` dataclass

**Example:**
```python
from app.services.delay_detection_phase2 import FeatureEngineer
from app.db.session import SessionLocal

db = SessionLocal()
case = db.query(Case).get(123)
density = FeatureEngineer.compute_adjournment_density(case, db)
print(f"Case has {density.adjournment_count}/{density.total_hearings} adjournments")
print(f"Trend: {density.trend}")
```

---

#### compute_tactic_frequency()

```python
@classmethod
def compute_tactic_frequency(
    case: Case,
    db: Session
) -> TacticFrequency:
    """Analyze frequency of each delay tactic in case adjournments."""
```

**Parameters:**
- `case: Case` - Case entity
- `db: Session` - Database session

**Returns:** `TacticFrequency` dataclass with distribution across 5 tactic categories

**Example:**
```python
tactics = FeatureEngineer.compute_tactic_frequency(case, db)
print(f"Proxy counsel: {tactics.proxy_counsel}")
print(f"Frivolous filing: {tactics.frivolous_filing}")
print(f"Total adjournments: {tactics.total}")
```

---

#### compute_party_driven_delay_score()

```python
@classmethod
def compute_party_driven_delay_score(
    case: Case,
    db: Session,
    density: Optional[AdjournmentDensity] = None,
    tactic_freq: Optional[TacticFrequency] = None
) -> PartyDrivenDelayScore:
    """Compute party-driven delay score based on tactical adjournments."""
```

**Parameters:**
- `case: Case` - Case entity
- `db: Session` - Database session
- `density: Optional[AdjournmentDensity]` - Pre-computed density (computed if None)
- `tactic_freq: Optional[TacticFrequency]` - Pre-computed frequencies (computed if None)

**Returns:** `PartyDrivenDelayScore` with composite 0-100 score

**Optimization Note:** Pass pre-computed `density` and `tactic_freq` to avoid duplicate queries for batch processing.

**Example:**
```python
score = FeatureEngineer.compute_party_driven_delay_score(case, db)
if score.score > 60:
    print("ALERT: High likelihood of party-driven delays")
    print(score.explanation)
```

---

#### compute_dormancy_variance()

```python
@classmethod
def compute_dormancy_variance(
    case: Case,
    db: Session
) -> DormancyVariance:
    """Analyze variance in gaps between consecutive hearings."""
```

**Parameters:**
- `case: Case` - Case entity
- `db: Session` - Database session

**Returns:** `DormancyVariance` with statistical gap analysis

**Example:**
```python
variance = FeatureEngineer.compute_dormancy_variance(case, db)
if variance.pattern_type == "prolonged_gaps":
    print(f"Unusual gaps detected: max {variance.max_gap_days} days")
```

---

#### compute_bench_hunting_index()

```python
@classmethod
def compute_bench_hunting_index(
    case: Case,
    db: Session
) -> BenchHuntingIndex:
    """Detect bench hunting patterns (judge/bench changes)."""
```

**Parameters:**
- `case: Case` - Case entity
- `db: Session` - Database session

**Returns:** `BenchHuntingIndex` with judge change analysis

**Example:**
```python
index = FeatureEngineer.compute_bench_hunting_index(case, db)
if index.pattern_strength > 0.6:
    print("Potential bench hunting detected")
    print(f"Judge changes: {index.judge_change_count}")
```

---

## Batch Processing Pattern

For efficient processing of multiple cases:

```python
from app.services.delay_detection_phase2 import FeatureEngineer

db = SessionLocal()
cases = db.query(Case).filter(Case.status == "PENDING").limit(1000)

results = []
for case in cases:
    # Compute all features for this case
    # Note: Some features reuse computed values for efficiency
    
    density = FeatureEngineer.compute_adjournment_density(case, db)
    tactic_freq = FeatureEngineer.compute_tactic_frequency(case, db)
    
    # Pass pre-computed values to avoid duplicate queries
    party_score = FeatureEngineer.compute_party_driven_delay_score(
        case, db,
        density=density,
        tactic_freq=tactic_freq
    )
    
    variance = FeatureEngineer.compute_dormancy_variance(case, db)
    bench_hunting = FeatureEngineer.compute_bench_hunting_index(case, db)
    
    results.append({
        "case_id": case.id,
        "density": density,
        "party_score": party_score,
        "variance": variance,
        "bench_hunting": bench_hunting,
    })
```

---

## Integration with Phase 1

Phase 2 features depend on Phase 1 adjournment tactic classification:

```python
from app.services.adjournment import AdjournmentTacticClassifier

# Phase 1: Identify what tactics are used
hearing = db.query(Hearing).get(456)
tactic = AdjournmentTacticClassifier.classify_tactic(hearing.outcome_text)
print(f"Tactic: {tactic.tactic}")

# Phase 2: Measure systemic patterns across hearing history
case = hearing.case
density = FeatureEngineer.compute_adjournment_density(case, db)
score = FeatureEngineer.compute_party_driven_delay_score(case, db)
```

---

## Data Model Interactions

Phase 2 uses existing Case and Hearing models without requiring schema changes:

| Model | Fields Used | Query Pattern |
|-------|------------|---------------|
| Case | case_id, status, filing_date | Primary filter entity |
| Hearing | date, outcome_type, outcome_text, judge_id | Analyzed for patterns |
| HearingOutcomeType | ADJOURNED, HEARD, DISPOSED | Outcome classification |

**Key Assumptions:**
- Hearings are chronologically sortable by `date`
- `outcome_type` accurately reflects hearing outcome
- `outcome_text` contains sufficient information for Phase 1 classification
- `judge_id` identifies bench assignments (can be NULL for adjournments)

---

## Performance Characteristics

### Query Complexity
- **Adjournment Density:** O(n) - Single pass through hearings
- **Tactic Frequency:** O(n) - Queries adjourned hearings + Phase 1 classification
- **Party Delay Score:** O(n) - Depends on density and tactic_freq
- **Dormancy Variance:** O(n) - Gap calculation across hearings
- **Bench Hunting:** O(n) - Judge sequence analysis

### Optimization Tips

1. **Use indices:** Ensure `idx_hearing_case_date` index is present
   ```sql
   CREATE INDEX idx_hearing_case_date ON hearings(case_id, date);
   ```

2. **Batch compute:** Reuse density/tactic results for party score
   ```python
   density = FeatureEngineer.compute_adjournment_density(case, db)
   score = FeatureEngineer.compute_party_driven_delay_score(
       case, db, density=density  # Pass pre-computed
   )
   ```

3. **Filter early:** Process only relevant cases
   ```python
   cases = db.query(Case).filter(
       Case.status.in_(["PENDING", "SCHEDULED"])
   ).order_by(Case.filing_date.desc())
   ```

---

## Testing

Comprehensive test suite in `backend/tests/test_delay_detection_phase2.py`:

**Test Coverage:**
- Empty case handling
- Single vs. multiple adjournments
- Trend detection (increasing/decreasing/stable)
- Tactic frequency distributions
- Party delay score calculation
- Dormancy pattern classification
- Bench hunting detection

**Running Tests:**
```bash
cd backend
pytest tests/test_delay_detection_phase2.py -v
pytest tests/test_delay_detection_phase2.py::TestAdjournmentDensity -v
pytest tests/test_delay_detection_phase2.py -k "test_trend_increasing"
```

---

## Next Steps: Phase 3

Phase 3 will implement:
- **Baseline Deviation Analysis** - Compare case metrics vs. baseline by court/case_type
- **Anomaly Detection** - Z-score standardization for outliers
- **Deliberate Delay Probability** - Final 0-100 score combining all phases
- **Case Alerting** - Automatic flagging of high-risk cases

---

## Troubleshooting

### Issue: Low adjournment data
**Symptom:** Pattern classification always returns "insufficient_data"
**Solution:** Minimum 3 hearings required. Check case has sufficient history.

### Issue: Inconsistent bench hunting scores
**Symptom:** Similar cases show vastly different bench hunting indices
**Solution:** Verify judge_id population in database. Some cases may have NULL judge assignments.

### Issue: Recurrence factor always 0
**Symptom:** Party-driven score only uses base components
**Solution:** Normal behavior. Recurrence factor amplifies when one tactic dominates.
