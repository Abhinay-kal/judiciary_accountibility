# Phase 4: Deliberate Delay Detection - REST API Documentation

## Overview

Phase 4 provides a complete REST API for the Deliberate Delay Detection system, exposing Phases 1-3 through HTTP endpoints. The API allows client applications and dashboards to:

1. **Calculate population baselines** from resolved cases
2. **Analyze individual cases** for deliberate delay probability
3. **Batch analyze multiple cases** for dashboard and reporting
4. **Inspect intermediate results** (features, z-scores) for debugging
5. **Monitor system health** and baseline freshness

## Base URL

```
http://localhost:8000/api/v1/delay-detection
```

All examples use this base URL. Replace with your deployment URL in production.

## API Endpoints

### 1. Health Check

**Endpoint:** `GET /health`

Returns the operational status of the delay detection system and component availability.

#### Request

```bash
curl -X GET http://localhost:8000/api/v1/delay-detection/health
```

#### Response (200 OK)

```json
{
  "status": "healthy",
  "phase1_available": true,
  "phase2_available": true,
  "phase3_available": true,
  "baseline_available": true,
  "baseline_sample_size": 2847,
  "baseline_last_updated": "2026-03-28T10:15:30Z",
  "message": "All systems operational"
}
```

#### Status Values

- **`healthy`** - All phases available and baseline calculated
- **`degraded`** - All phases available but baseline not yet calculated
- **`error`** - One or more phases unavailable

#### Use Cases

- Pre-flight checks before running analyses
- Dashboard health status indicators
- Monitoring system availability
- Determining if baseline needs recalculation

---

### 2. Get Baseline Metrics

**Endpoint:** `GET /baseline`

Retrieve or calculate population baseline metrics from all resolved cases. The baseline defines the "normal" range for each feature across the court system.

#### Request

```bash
# Get current baseline (cached)
curl -X GET http://localhost:8000/api/v1/delay-detection/baseline

# Force recalculation from database
curl -X GET "http://localhost:8000/api/v1/delay-detection/baseline?recalculate=true"
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `recalculate` | boolean | false | Force recalculation from all resolved cases |

#### Response (200 OK)

```json
{
  "density_mean": 0.12,
  "density_std": 0.08,
  "party_score_mean": 1.45,
  "party_score_std": 0.67,
  "dormancy_cv_mean": 0.34,
  "dormancy_cv_std": 0.18,
  "bench_hunting_mean": 0.28,
  "bench_hunting_std": 0.15,
  "sample_size": 2847,
  "calculation_date": "2026-03-28T08:00:00Z",
  "status": "success"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `density_mean` | float | Mean adjournment density (0-1) |
| `density_std` | float | Std deviation of density |
| `party_score_mean` | float | Mean party-driven delay score (0-4) |
| `party_score_std` | float | Std deviation of party score |
| `dormancy_cv_mean` | float | Mean dormancy coefficient of variation |
| `dormancy_cv_std` | float | Std deviation of dormancy CV |
| `bench_hunting_mean` | float | Mean bench hunting index (0-1) |
| `bench_hunting_std` | float | Std deviation of bench hunting |
| `sample_size` | int | Number of resolved cases used |
| `calculation_date` | ISO8601 | When baseline was calculated |
| `status` | string | "success" or "error" |

#### HTTP Status Codes

- **200 OK** - Baseline retrieved or calculated successfully
- **500 Internal Server Error** - Baseline calculation failed

#### Use Cases

- Dashboard displays of population statistics
- Detecting when baseline needs refresh (e.g., after new cases disposed)
- Understanding what "normal" delay patterns look like
- Verifying that sufficient historical data exists (check `sample_size`)

#### Caching

- Baselines are cached in-memory for 1 hour
- Database cache persists across server restarts
- Use `recalculate=true` to refresh after bulk case disposals

---

### 3. Analyze Single Case

**Endpoint:** `GET /case/{case_id}`

Analyze a single case for deliberate delay probability. Runs the complete Phase 1→2→3 pipeline:

1. **Phase 1**: Classify adjournment tactics from hearing outcomes
2. **Phase 2**: Extract delay-related features
3. **Phase 3**: Compare against baseline and compute probability

#### Request

```bash
curl -X GET http://localhost:8000/api/v1/delay-detection/case/42
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_id` | int | The database ID of the case |

#### Response (200 OK)

```json
{
  "case_id": 42,
  "case_number": "WP/1234/2021",
  "probability": 82.5,
  "percentile": 88.3,
  "risk_level": "high",
  "confidence": 0.87,
  "primary_drivers": [
    "High bench hunting (z=2.8)",
    "Elevated party score (z=2.1)"
  ],
  "anomalies": [
    "bench_hunting_z: 2.8",
    "party_score_z: 2.1"
  ],
  "explanation": "Case exhibits high probability of deliberate delay. Primary anomalies: elevated bench hunting index (2.8 std above population) suggesting judge-switching behavior; elevated party-driven delay score (2.1 std above) indicating multiple delay tactics. Risk level: HIGH.",
  "analysis_timestamp": "2026-03-28T12:34:56Z",
  "status": "success"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | int | Case database ID |
| `case_number` | string | Human-readable case identifier |
| `probability` | float | Probability of deliberate delay (0-100) |
| `percentile` | float | Percentile rank vs population (0-100) |
| `risk_level` | string | "low", "moderate", "high", or "extreme" |
| `confidence` | float | Confidence in assessment (0.3-1.0) |
| `primary_drivers` | array | Top 1-3 anomalies driving the probability |
| `anomalies` | array | All detected anomalies (z > 2 std) |
| `explanation` | string | Plain-language explanation |
| `analysis_timestamp` | ISO8601 | When analysis was performed |
| `status` | string | "success" or "error" |

#### Risk Levels

| Level | Percentile | Probability | Interpretation |
|-------|-----------|-------------|-----------------|
| `low` | 0-25 | 0-25 | Normal delay pattern |
| `moderate` | 25-50 | 25-50 | Some anomalies but not extreme |
| `high` | 50-75 | 50-75 | Likely deliberate delay tactics |
| `extreme` | 75-100 | 75-100 | Strong evidence of deliberate delay |

#### HTTP Status Codes

- **200 OK** - Case analyzed successfully
- **404 Not Found** - Case ID does not exist
- **422 Unprocessable Entity** - Invalid case ID format
- **502 Bad Gateway** - Analysis failed

#### Error Response (404)

```json
{
  "detail": "Case with ID 99999 not found"
}
```

#### Use Cases

- Dashboard case detail page
- Risk flagging systems
- Case prioritization for judicial review
- ROI analysis for court efficiency improvements

#### Performance

- Typical analysis: 50-100ms per case
- Includes baseline lookup, feature extraction, and probability calculation
- Suitable for real-time dashboard queries

---

### 4. Get Case Features

**Endpoint:** `GET /case/{case_id}/features`

Retrieve the extracted Phase 2 features for a case (for debugging/inspection). Shows the raw feature values before z-score standardization.

#### Request

```bash
curl -X GET http://localhost:8000/api/v1/delay-detection/case/42/features
```

#### Response (200 OK)

```json
{
  "case_id": 42,
  "case_number": "WP/1234/2021",
  "adjournment_density": 0.18,
  "party_driven_score": 2.5,
  "dormancy_cv": 0.42,
  "bench_hunting_index": 0.65
}
```

#### Response Fields

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `case_id` | int | - | Case database ID |
| `case_number` | string | - | Human-readable case ID |
| `adjournment_density` | float | 0-1 | Adjournments per day of case life |
| `party_driven_score` | float | 0-4 | Estimated party-driven tactics |
| `dormancy_cv` | float | 0-∞ | Coefficient of variation in delays |
| `bench_hunting_index` | float | 0-1 | Judge-switching pattern intensity |

#### Use Cases

- Debugging why a case received a particular risk level
- Verifying feature calculation accuracy
- Understanding feature distributions
- Data quality checks

---

### 5. Get Z-Scores

**Endpoint:** `GET /case/{case_id}/z-scores`

Retrieve standardized z-scores showing how each feature deviates from the population mean. Useful for understanding which features are driving the probability.

#### Request

```bash
curl -X GET http://localhost:8000/api/v1/delay-detection/case/42/z-scores
```

#### Response (200 OK)

```json
{
  "density_z": 0.8,
  "party_score_z": 2.1,
  "dormancy_cv_z": -0.5,
  "bench_hunting_z": 2.8,
  "composite_z": 1.95,
  "anomalies": [
    "party_score_z: 2.1",
    "bench_hunting_z: 2.8"
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `density_z` | float | Z-score for adjournment density |
| `party_score_z` | float | Z-score for party-driven score |
| `dormancy_cv_z` | float | Z-score for dormancy CV |
| `bench_hunting_z` | float | Z-score for bench hunting |
| `composite_z` | float | Weighted composite z-score |
| `anomalies` | array | Features with \|z\| > 2 (outliers) |

#### Z-Score Interpretation

- **z = 0**: Feature matches population mean exactly
- **z = 1**: Feature is 1 std dev above mean (68th percentile)
- **z = 2**: Feature is 2 std devs above mean (95th percentile) - **ANOMALY**
- **z = -1**: Feature is 1 std dev below mean
- **z > 2 or z < -2**: Statistical outlier (99% confidence)

#### Use Cases

- Advanced diagnostics and debugging
- Understanding which features deviate from normal
- Data quality verification
- Research on delay patterns

---

### 6. Batch Analyze Cases

**Endpoint:** `POST /batch`

Analyze multiple cases (1-1000) in a single request. Returns individual results plus aggregate statistics.

#### Request

```bash
# Query parameter format
curl -X POST "http://localhost:8000/api/v1/delay-detection/batch?case_ids=42,43,44"

# Alternative: Pass as multiple parameters
curl -X POST "http://localhost:8000/api/v1/delay-detection/batch" \
  -d "case_ids=42&case_ids=43&case_ids=44"
```

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `case_ids` | list[int] | Yes | Comma-separated case IDs (max 1000) |

#### Response (200 OK)

```json
{
  "analysis_type": "batch_delay_analysis",
  "total_cases_analyzed": 50,
  "success_count": 48,
  "error_count": 2,
  "results": [
    {
      "case_id": 42,
      "case_number": "WP/1234/2021",
      "probability": 82.5,
      "risk_level": "high",
      "confidence": 0.87,
      "primary_drivers": ["High bench hunting (z=2.8)"]
    },
    {
      "case_id": 43,
      "case_number": "WP/1235/2021",
      "probability": 21.3,
      "risk_level": "low",
      "confidence": 0.92,
      "primary_drivers": []
    }
    // ... more results
  ],
  "summary_stats": {
    "count": 48,
    "mean": 38.7,
    "min": 0.0,
    "max": 95.2,
    "median": 32.1,
    "stdev": 21.4
  },
  "analysis_timestamp": "2026-03-28T12:34:56Z",
  "version": "1.0"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `analysis_type` | string | Always "batch_delay_analysis" |
| `total_cases_analyzed` | int | Total input case IDs |
| `success_count` | int | Cases analyzed successfully |
| `error_count` | int | Cases with errors |
| `results` | array | Individual case analysis results |
| `summary_stats` | object | Aggregate statistics (count, mean, std, min, max, median) |
| `analysis_timestamp` | ISO8601 | When batch started |
| `version` | string | API version |

#### Summary Statistics

Contains aggregate metrics useful for dashboards:

- **count**: Number of successfully analyzed cases
- **mean**: Average probability across cases
- **median**: Median probability (50th percentile)
- **min**: Minimum probability
- **max**: Maximum probability
- **stdev**: Standard deviation (if count > 1)

#### Batch Limits

- Minimum: 1 case
- Maximum: 1000 cases per request
- For larger batches, submit multiple requests

#### Performance

- Typical batch of 100 cases: 5-10 seconds
- Scales linearly with case count
- Caches baseline for batch operations

#### HTTP Status Codes

- **200 OK** - Batch analysis completed (some may have failed)
- **400 Bad Request** - Invalid case_ids parameter
- **422 Unprocessable Entity** - Validation error
- **502 Bad Gateway** - Batch analysis failed

#### Error Response (400)

```json
{
  "detail": "Maximum 1000 cases per batch request"
}
```

#### Use Cases

- Generate dashboard with all high-risk cases
- Court efficiency analysis (compare courts/judges)
- Report generation (monthly judicial performance)
- Bulk export for further analysis

---

## Response Status Codes

| Code | Meaning | Example Causes |
|------|---------|-----------------|
| 200 | Success | Analysis completed, data retrieved |
| 400 | Bad Request | Invalid parameters, max batch size exceeded |
| 404 | Not Found | Case ID doesn't exist |
| 422 | Validation Error | Invalid type (e.g., string case_id) |
| 500 | Internal Error | Baseline calc failed |
| 502 | Bad Gateway | Phase service unavailable |

---

## Error Handling

### Standard Error Response

All errors return JSON with this structure:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Errors

#### Case Not Found

```
GET /case/99999
→ 404
{
  "detail": "Case with ID 99999 not found"
}
```

**Solutions:**
- Verify case ID value
- Check if case was deleted
- Use a known valid case ID from your database

#### Invalid Case ID Format

```
GET /case/not-a-number
→ 422
{
  "detail": "value is not a valid integer"
}
```

**Solutions:**
- Pass case ID as integer, not string
- Remove quotes or formatting

#### Baseline Not Available

```
GET /baseline
→ 200
{
  "status": "error",
  "sample_size": 0,
  "message": "No resolved cases available..."
}
```

**Solutions:**
- Dispose some cases first to create baseline
- Use `recalculate=true` to force calculation

#### Batch Size Exceeded

```
POST /batch?case_ids=1,2,...,1001
→ 400
{
  "detail": "Maximum 1000 cases per batch request"
}
```

**Solutions:**
- Split into multiple batch requests
- Reduce case_ids list to ≤ 1000

---

## Usage Examples

### Example 1: Check System Health

```bash
# Check if system is ready
curl -X GET http://localhost:8000/api/v1/delay-detection/health

# If status is "degraded", recalculate baseline
curl -X GET "http://localhost:8000/api/v1/delay-detection/baseline?recalculate=true"
```

### Example 2: Analyze Single Case

```bash
# Get analysis for case 42
curl -X GET http://localhost:8000/api/v1/delay-detection/case/42

# If result looks off, inspect features
curl -X GET http://localhost:8000/api/v1/delay-detection/case/42/features

# Look at z-scores to see which features are anomalous
curl -X GET http://localhost:8000/api/v1/delay-detection/case/42/z-scores
```

### Example 3: Dashboard - High Risk Cases

```bash
# Get all high-risk cases (IDs 1-100)
curl -X POST "http://localhost:8000/api/v1/delay-detection/batch?case_ids=$(seq -s, 1 100)"

# Parse summary_stats to show statistics
# Parse results array to show individual cases
```

### Example 4: Weekly Report

```bash
# Generate report for all disposed cases this week
curl -X GET "http://localhost:8000/api/v1/delay-detection/baseline?recalculate=true"

# Batch analyze high-risk case candidates (e.g., age > 3 years)
curl -X POST "http://localhost:8000/api/v1/delay-detection/batch?case_ids=..."

# Export summary_stats to PDF report
```

### Example 5: Python Client

```python
import requests

BASE_URL = "http://localhost:8000/api/v1/delay-detection"

# Health check
response = requests.get(f"{BASE_URL}/health")
if response.status_code == 200:
    health = response.json()
    print(f"System Status: {health['status']}")

# Analyze single case
response = requests.get(f"{BASE_URL}/case/42")
result = response.json()
print(f"Risk Level: {result['risk_level']}")
print(f"Probability: {result['probability']:.1f}%")

# Batch analyze
case_ids = [1, 2, 3, 4, 5]
params = {"case_ids": ",".join(map(str, case_ids))}
response = requests.post(f"{BASE_URL}/batch", params=params)
batch_result = response.json()
print(f"Analyzed: {batch_result['success_count']} cases")
print(f"Mean Probability: {batch_result['summary_stats']['mean']:.1f}%")
```

---

## Performance Guidelines

### Endpoint Latencies

| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| `/health` | 5ms | 15ms | 25ms |
| `/baseline` (cached) | 10ms | 20ms | 50ms |
| `/case/{id}` | 50ms | 80ms | 150ms |
| `/case/{id}/features` | 40ms | 70ms | 120ms |
| `/case/{id}/z-scores` | 45ms | 75ms | 130ms |
| `/batch (100 cases)` | 5s | 8s | 12s |

### Optimization Tips

1. **Cache baseline**: Don't call `/baseline` repeatedly - cache for 1 hour
2. **Batch operations**: Use `/batch` instead of multiple `/case/{id}` calls
3. **Reuse results**: Don't re-analyze same case unless data changed
4. **Monitor latency**: Alert if API responses exceed 5x baseline

### Scalability

- Single server: ~20 cases/sec (50ms latency)
- 100 case batch: 5-8 seconds
- 1000 case batch: 50-80 seconds
- Load balancing recommended for 100+ requests/min

---

## Best Practices

### 1. Always Check Health First

```bash
# Before doing work, check system status
curl http://localhost:8000/api/v1/delay-detection/health
```

### 2. Use Batch When Possible

```bash
# Good: Batch 100 cases
POST /batch?case_ids=1,2,3,...,100

# Bad: 100 individual requests
for i in 1..100:
    GET /case/{i}
```

### 3. Handle Errors Gracefully

- Retry failed requests with exponential backoff
- Monitor `error_count` in batch responses
- Log failures for investigation

### 4. Cache Results

- Cache case analysis results for 24 hours
- Recalculate only if case data changed
- Use `/baseline?recalculate=true` periodically (weekly)

### 5. Monitor Production

- Alert on `status != healthy`
- Track response times (P95 latency)
- Monitor error rates (5xx responses)
- Log all batch analysis runs

---

## FAQ

### Q: How often is the baseline calculated?

**A:** Baseline is cached for 1 hour in memory and persisted in database. Use `?recalculate=true` if you've disposed many cases and want immediate update.

### Q: Can I analyze cases that aren't disposed yet?

**A:** Yes! The API analyzes any case, disposed or pending. Pending cases can show emerging delay patterns.

### Q: What does "confidence" mean?

**A:** Confidence ranges 0.3-1.0. Higher is more reliable. Low confidence (0.3) means limited data points; high confidence (0.9+) means strong statistical certainty.

### Q: How do I know which features are driving the probability?

**A:** Check `primary_drivers` in the response. For detailed breakdown, call `/case/{id}/z-scores` to see all z-scores.

### Q: Can I export results?

**A:** Yes! The API returns JSON which can be exported to CSV, Excel, or PDF by your application. Batch endpoint is best for bulk export.

### Q: What if batch analysis fails for some cases?

**A:** Check `error_count` in batch response. Successfully analyzed cases appear in `results` array. Failed cases are silently skipped.

---

## Version History

### v1.0 (Current)

- Basic CRUD operations for baseline and case analysis
- Batch analysis (1-1000 cases)
- All three phases integrated
- Caching support
- Full error handling

### Planned Features (v1.1+)

- Batch analysis progress tracking
- Webhooks for async processing
- Custom percentile lookup tables by court/state
- Case update subscriptions
- Advanced filtering (by court, date range, etc.)

---

## Support

For issues, questions, or feature requests:

1. Check this documentation
2. Review [Phase 3 Technical Docs](./DELIBERATE_DELAY_DETECTION_PHASE3.md) for detailed algorithms
3. See integration test examples in `tests/test_api_delay_detection_phase4.py`
4. Contact the development team

---

Generated: March 28, 2026
API Version: 1.0
Last Updated: Phase 4 Implementation Complete
