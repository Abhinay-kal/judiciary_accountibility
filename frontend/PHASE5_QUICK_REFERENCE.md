# Phase 5: Frontend Dashboard - Quick Reference

## 🚀 Getting Started

### Access the Dashboard
```
Dashboard URL: http://localhost:3000/delay-detection
Hub Integration: http://localhost:3000/hub?tab=delay_detection
```

### Quick Links
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/delay-detection/health
- **Swagger UI**: http://localhost:8000/docs

## 📊 Key Components

### Single Case Analysis
```bash
# Search for case ID 123
- Navigate to "Single Case" tab
- Enter case ID: 123
- View analysis with:
  ├─ Probability (0-100%)
  ├─ Risk level badge
  ├─ Feature breakdown
  ├─ Primary drivers
  └─ Anomalies detected
```

### Batch Analysis
```bash
# Analyze multiple cases
Cases: 100, 101, 102
Or: 100
    101
    102

Results:
- Total cases analyzed
- Success/failure counts
- Summary statistics
- Individual results table
```

### Population Baseline
```bash
# View population-wide metrics
- Sample size: N cases
- Feature means and standard deviations
- Recalculate button for on-demand updates
- Visual chart of feature distribution
```

## 🔧 Environment Setup

### Frontend .env.local
```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

### Backend Requirements
- Phase 4 API running on port 8000
- Database connection active
- Population baseline cached or calculated

## 📝 Component API Reference

### DelayDetectionAnalysis
```typescript
<DelayDetectionAnalysis caseId={123} />
```

### BaselineMetrics
```typescript
<BaselineMetrics />
```

### BatchDelayAnalysis
```typescript
<BatchDelayAnalysis />
```

### CaseDelaySearch
```typescript
<CaseDelaySearch />
```

## 🧪 Testing the API

### Test Single Case
```bash
curl -X GET "http://localhost:8000/api/v1/delay-detection/case/1" \
  -H "Accept: application/json"
```

### Test Batch Analysis
```bash
curl -X POST "http://localhost:8000/api/v1/delay-detection/batch" \
  -H "Content-Type: application/json" \
  -d '{"case_ids": [1, 2, 3]}'
```

### Test Baseline
```bash
curl -X GET "http://localhost:8000/api/v1/delay-detection/baseline" \
  -H "Accept: application/json"
```

### Test Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/delay-detection/health" \
  -H "Accept: application/json"
```

## 🎨 UI Themes

### Risk Level Colors
| Level | Color | Probability |
|-------|-------|-------------|
| Low | Green (#10b981) | 0-25% |
| Moderate | Yellow (#f59e0b) | 25-50% |
| High | Orange (#f97316) | 50-75% |
| Extreme | Red (#ef4444) | 75-100% |

## ⚡ Performance Tips

1. **Use Batch Analysis** for 100+ cases (faster than individual calls)
2. **Cache Baseline** - Recalculate only when data significantly changes
3. **Featured Visualization** - Charts load after data is ready
4. **Lazy Loading** - Components load dynamically on tab selection

## 🐛 Debugging

### Check Component Rendering
```javascript
// In browser console
console.log('API Base:', process.env.NEXT_PUBLIC_API_BASE)
```

### Monitor Network Calls
1. Open DevTools → Network tab
2. Look for requests to `/api/v1/delay-detection/*`
3. Check response status and payload

### Backend Logs
```bash
docker-compose logs backend | grep delay-detection
```

## 📚 Feature Matrix

| Feature | Status | Component |
|---------|--------|-----------|
| Single Case Analysis | ✅ Complete | DelayDetectionAnalysis |
| Batch Processing | ✅ Complete | BatchDelayAnalysis |
| Population Baseline | ✅ Complete | BaselineMetrics |
| Risk Visualization | ✅ Complete | RiskBadge |
| Feature Charts | ✅ Complete | AnalysisChart |
| Hub Integration | ✅ Complete | Hub page |
| Error Handling | ✅ Complete | All components |
| Mobile Responsive | ✅ Complete | Tailwind CSS |
| Type Safety | ✅ Complete | TypeScript |
| Loading States | ✅ Complete | Skeleton screens |

## 🔗 Integration Flow

```
Hub Page (main navigation)
    ↓
Delay Detection Tab
    ├─ Overview (info cards)
    ├─ Single Case (search interface)
    ├─ Batch Analysis (multi-case)
    └─ Population Baseline (system metrics)
        ↓
    Phase 4 REST API (/delay-detection/*)
        ↓
    Phase 1-3 ML Pipeline
        └─ Results displayed with visualizations
```

## 🚨 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| API calls failing | Check NEXT_PUBLIC_API_BASE env var |
| Components not rendering | Clear .next/ cache and rebuild |
| Charts not displaying | Verify data structure matches types |
| Slow performance | Use batch analysis for multiple cases |
| Hub tab not showing | Verify hub page was updated correctly |

## 📊 Expected Response Times

| Operation | Expected Time |
|-----------|---------------|
| Single case | 50-100ms |
| Batch (100 cases) | 5-10s |
| Baseline load | 50-200ms |
| Chart render | 100-300ms |

## 🎯 Next Steps

After Phase 5 deployment:
1. Monitor API response times and errors
2. Collect user feedback on dashboard UX
3. Plan Phase 5.1: Export functionality
4. Consider Phase 5.2: Historical trends
5. Evaluate Phase 6: Advanced filtering

## 📞 Support

For issues or questions:
1. Check backend logs: `docker-compose logs backend`
2. Review API documentation: http://localhost:8000/docs
3. Check browser DevTools for JavaScript errors
4. Test API endpoints directly with curl

---

**Phase 5 Status**: ✅ COMPLETE
**Components**: 7 new + 1 updated
**Test Coverage**: All major flows tested
**Ready for Production**: Yes
