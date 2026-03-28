"use client";

import { FormEvent, useState } from "react";

interface BatchAnalysisResult {
  total_cases_analyzed: number;
  success_count: number;
  error_count: number;
  results: Array<{
    case_id: number;
    case_number: string;
    probability: number;
    risk_level: string;
    confidence: number;
  }>;
  summary_stats: {
    mean: number;
    std: number;
    min: number;
    max: number;
    median: number;
  };
  analysis_timestamp: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function BatchDelayAnalysis() {
  const [caseIdsInput, setCaseIdsInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BatchAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();

    try {
      setLoading(true);
      setError(null);

      // Parse case IDs
      const caseIds = caseIdsInput
        .split(/[\s,\n]+/)
        .map((id) => parseInt(id.trim()))
        .filter((id) => !isNaN(id));

      if (caseIds.length === 0) {
        setError("Please enter at least one case ID");
        setLoading(false);
        return;
      }

      if (caseIds.length > 1000) {
        setError("Maximum 1000 cases per batch analysis");
        setLoading(false);
        return;
      }

      // Call batch API
      const response = await fetch(`${API_BASE}/delay-detection/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_ids: caseIds }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = (await response.json()) as BatchAnalysisResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h3 className="font-semibold text-lg mb-4">Batch Delay Analysis</h3>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink/70 mb-2">
              Case IDs (comma or newline separated, max 1000)
            </label>
            <textarea
              value={caseIdsInput}
              onChange={(e) => setCaseIdsInput(e.target.value)}
              placeholder="Enter case IDs: 123, 456, 789&#10;or paste one per line"
              className="w-full h-32 rounded-lg border border-ink/20 bg-white p-3 font-mono text-sm"
              disabled={loading}
            />
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading || !caseIdsInput.trim()}
              className="flex-1 rounded-lg bg-ocean px-4 py-2 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-ocean/90 transition"
            >
              {loading ? "Analyzing..." : "Analyze Cases"}
            </button>
            <button
              type="button"
              onClick={() => {
                setCaseIdsInput("");
                setResult(null);
                setError(null);
              }}
              className="rounded-lg border border-ink/20 px-4 py-2 font-medium hover:bg-ink/5 transition"
            >
              Clear
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-900 font-medium">Error</p>
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="card space-y-3">
            <p className="font-semibold text-lg">Analysis Summary</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="space-y-1">
                <p className="text-sm text-ink/70">Total Cases</p>
                <p className="text-2xl font-bold text-ocean">{result.total_cases_analyzed}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-ink/70">Successful</p>
                <p className="text-2xl font-bold text-green-600">{result.success_count}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-ink/70">Failed</p>
                <p className="text-2xl font-bold text-red-600">{result.error_count}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-ink/70">Avg Probability</p>
                <p className="text-2xl font-bold text-sky-600">
                  {result.summary_stats.mean.toFixed(1)}%
                </p>
              </div>
            </div>
          </div>

          {/* Statistics */}
          <div className="card space-y-3">
            <p className="font-semibold text-lg">Statistics</p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-sm">
              <div className="space-y-1">
                <p className="text-ink/70">Minimum</p>
                <p className="font-mono font-semibold">{result.summary_stats.min.toFixed(1)}%</p>
              </div>
              <div className="space-y-1">
                <p className="text-ink/70">Median</p>
                <p className="font-mono font-semibold">{result.summary_stats.median.toFixed(1)}%</p>
              </div>
              <div className="space-y-1">
                <p className="text-ink/70">Mean</p>
                <p className="font-mono font-semibold">{result.summary_stats.mean.toFixed(1)}%</p>
              </div>
              <div className="space-y-1">
                <p className="text-ink/70">Std Dev</p>
                <p className="font-mono font-semibold">{result.summary_stats.std.toFixed(1)}%</p>
              </div>
              <div className="space-y-1">
                <p className="text-ink/70">Maximum</p>
                <p className="font-mono font-semibold">{result.summary_stats.max.toFixed(1)}%</p>
              </div>
            </div>
          </div>

          {/* Results Table */}
          {result.results.length > 0 && (
            <div className="card space-y-3 overflow-auto">
              <p className="font-semibold text-lg">Individual Results</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink/10">
                    <th className="text-left py-2 px-3 font-medium text-ink/70">Case #</th>
                    <th className="text-right py-2 px-3 font-medium text-ink/70">Probability</th>
                    <th className="text-right py-2 px-3 font-medium text-ink/70">Confidence</th>
                    <th className="text-center py-2 px-3 font-medium text-ink/70">Risk Level</th>
                  </tr>
                </thead>
                <tbody>
                  {result.results.slice(0, 20).map((res) => (
                    <tr key={res.case_id} className="border-b border-ink/5 hover:bg-ink/2">
                      <td className="py-2 px-3 font-mono text-blue-600 hover:underline cursor-pointer">
                        {res.case_number}
                      </td>
                      <td className="text-right py-2 px-3 font-semibold">{res.probability.toFixed(1)}%</td>
                      <td className="text-right py-2 px-3">
                        {(res.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="text-center py-2 px-3">
                        <RiskLevelBadge risk={res.risk_level} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.results.length > 20 && (
                <p className="text-sm text-ink/70 italic">
                  Showing 20 of {result.results.length} results
                </p>
              )}
            </div>
          )}

          {/* Timestamp */}
          <p className="text-xs text-ink/50 text-center">
            Analysis performed: {new Date(result.analysis_timestamp).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}

function RiskLevelBadge({ risk }: { risk: string }) {
  const colors = {
    low: "bg-green-100 text-green-700",
    moderate: "bg-yellow-100 text-yellow-700",
    high: "bg-orange-100 text-orange-700",
    extreme: "bg-red-100 text-red-700",
  };
  const color = colors[risk as keyof typeof colors] || colors.low;
  return (
    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${color}`}>
      {risk.charAt(0).toUpperCase() + risk.slice(1)}
    </span>
  );
}
