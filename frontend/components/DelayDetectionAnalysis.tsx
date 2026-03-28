"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const RiskBadge = dynamic(
  () => import("./RiskBadge").then((module) => module.RiskBadge),
  { ssr: false, loading: () => <div className="h-6 w-20 bg-ink/10 rounded-full animate-pulse" /> }
);

const AnalysisChart = dynamic(
  () => import("./AnalysisChart").then((module) => module.AnalysisChart),
  { ssr: false, loading: () => <div className="h-64 bg-ink/10 rounded-lg animate-pulse" /> }
);

interface DelayAnalysisResponse {
  status: string;
  case_id: number;
  case_number: string;
  probability: number; // 0-100
  percentile: number; // 0-100
  risk_level: "low" | "moderate" | "high" | "extreme";
  confidence: number; // 0.3-1.0
  primary_drivers: string[];
  anomalies: string[];
  explanation: string;
  analysis_timestamp: string;
}

interface CaseFeatureValues {
  case_id: number;
  case_number: string;
  adjournment_density: number;
  party_driven_score: number;
  dormancy_cv: number;
  bench_hunting_index: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function DelayDetectionAnalysis({ caseId }: { caseId: number }) {
  const [analysis, setAnalysis] = useState<DelayAnalysisResponse | null>(null);
  const [features, setFeatures] = useState<CaseFeatureValues | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    async function fetchAnalysis() {
      try {
        setLoading(true);
        const res = await fetch(
          `${API_BASE}/delay-detection/case/${caseId}`,
          { cache: "no-store" }
        );
        if (!res.ok) {
          throw new Error(`Failed to fetch analysis: ${res.status}`);
        }
        const data = (await res.json()) as DelayAnalysisResponse;
        setAnalysis(data);

        // Fetch features for debugging
        const featureRes = await fetch(
          `${API_BASE}/delay-detection/case/${caseId}/features`,
          { cache: "no-store" }
        );
        if (featureRes.ok) {
          const featureData = (await featureRes.json()) as CaseFeatureValues;
          setFeatures(featureData);
        }

        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setAnalysis(null);
      } finally {
        setLoading(false);
      }
    }

    fetchAnalysis();
  }, [caseId]);

  if (loading) {
    return (
      <div className="card space-y-4 animate-pulse">
        <div className="h-8 w-48 bg-ink/10 rounded-lg" />
        <div className="h-32 bg-ink/10 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card bg-red-50 border border-red-200 p-4 rounded-lg">
        <p className="font-semibold text-red-900">Analysis Error</p>
        <p className="text-sm text-red-700 mt-2">{error}</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="card p-4 text-center">
        <p className="text-ink/70">No analysis available for this case</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Main Analysis Card */}
      <div className="card space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-lg">Deliberate Delay Detection</h3>
            <p className="text-sm text-ink/70">Case {analysis.case_number}</p>
          </div>
          <RiskBadge riskLevel={analysis.risk_level} probability={analysis.probability} />
        </div>

        {/* Probability Display */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <p className="text-sm font-medium text-ink/70">Delay Probability</p>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold text-ocean">{analysis.probability.toFixed(1)}%</span>
              <span className="text-sm text-ink/70">
                Percentile: {analysis.percentile.toFixed(0)}th
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-ink/70">Model Confidence</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-green-600">
                {(analysis.confidence * 100).toFixed(0)}%
              </span>
              <span className="text-xs text-ink/70">
                ({analysis.confidence.toFixed(2)})
              </span>
            </div>
          </div>
        </div>

        {/* Analysis Chart */}
        {features && (
          <div>
            <AnalysisChart features={features} probability={analysis.probability} />
          </div>
        )}

        {/* Primary Drivers */}
        {analysis.primary_drivers.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-ink/70">Primary Drivers</p>
            <ul className="space-y-1">
              {analysis.primary_drivers.map((driver, idx) => (
                <li key={idx} className="text-sm flex items-center gap-2">
                  <span className="h-2 w-2 bg-sky-500 rounded-full" />
                  {driver}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Anomalies */}
        {analysis.anomalies.length > 0 && (
          <div className="space-y-2 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
            <p className="text-sm font-medium text-yellow-900">Detected Anomalies</p>
            <ul className="space-y-1">
              {analysis.anomalies.map((anomaly, idx) => (
                <li key={idx} className="text-sm text-yellow-800 flex items-center gap-2">
                  <span className="text-lg">⚠️</span>
                  {anomaly}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Explanation */}
        <div className="space-y-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-sm font-medium text-blue-900">Analysis Summary</p>
          <p className="text-sm text-blue-800">{analysis.explanation}</p>
        </div>

        {/* Additional Details Toggle */}
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-sm text-ocean hover:underline font-medium"
        >
          {showDetails ? "Hide" : "Show"} Feature Details
        </button>

        {/* Feature Details */}
        {showDetails && features && (
          <div className="space-y-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-sm font-medium text-gray-900">Feature Values</p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-gray-600">Adjournment Density</p>
                <p className="font-mono text-gray-900">{features.adjournment_density.toFixed(3)}</p>
              </div>
              <div>
                <p className="text-gray-600">Party Driven Score</p>
                <p className="font-mono text-gray-900">{features.party_driven_score.toFixed(3)}</p>
              </div>
              <div>
                <p className="text-gray-600">Dormancy CV</p>
                <p className="font-mono text-gray-900">{features.dormancy_cv.toFixed(3)}</p>
              </div>
              <div>
                <p className="text-gray-600">Bench Hunting Index</p>
                <p className="font-mono text-gray-900">{features.bench_hunting_index.toFixed(3)}</p>
              </div>
            </div>
          </div>
        )}

        {/* Timestamp */}
        <p className="text-xs text-ink/50 border-t border-ink/10 pt-3">
          Analysis performed: {new Date(analysis.analysis_timestamp).toLocaleString()}
        </p>
      </div>
    </div>
  );
}
