"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface BaselineResponse {
  status: string;
  density_mean: number;
  density_std: number;
  party_score_mean: number;
  party_score_std: number;
  dormancy_cv_mean: number;
  dormancy_cv_std: number;
  bench_hunting_mean: number;
  bench_hunting_std: number;
  sample_size: number;
  calculation_date: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function BaselineMetrics() {
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);

  async function fetchBaseline(recalculate = false) {
    try {
      setLoading(true);
      const url = new URL(`${API_BASE}/delay-detection/baseline`);
      if (recalculate) {
        url.searchParams.append("recalculate", "true");
      }
      const response = await fetch(url.toString(), { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Failed to fetch baseline: ${response.status}`);
      }
      const data = (await response.json()) as BaselineResponse;
      setBaseline(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchBaseline();
  }, []);

  async function handleRecalculate() {
    setRecalculating(true);
    await fetchBaseline(true);
    setRecalculating(false);
  }

  if (loading && !baseline) {
    return (
      <div className="card space-y-4 animate-pulse">
        <div className="h-8 w-48 bg-ink/10 rounded-lg" />
        <div className="h-64 bg-ink/10 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card bg-red-50 border border-red-200 p-4 rounded-lg">
        <p className="font-semibold text-red-900">Error Loading Baseline</p>
        <p className="text-sm text-red-700 mt-2">{error}</p>
      </div>
    );
  }

  if (!baseline) {
    return (
      <div className="card p-4 text-center">
        <p className="text-ink/70">No baseline data available</p>
      </div>
    );
  }

  // Prepare chart data
  const chartData = [
    {
      metric: "Adjournment\nDensity",
      mean: baseline.density_mean,
      std: baseline.density_std,
    },
    {
      metric: "Party Score",
      mean: baseline.party_score_mean,
      std: baseline.party_score_std,
    },
    {
      metric: "Dormancy CV",
      mean: baseline.dormancy_cv_mean,
      std: baseline.dormancy_cv_std,
    },
    {
      metric: "Bench Hunting",
      mean: baseline.bench_hunting_mean,
      std: baseline.bench_hunting_std,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-lg">Population Baseline</h3>
            <p className="text-sm text-ink/70">Population-wide metrics for anomaly detection</p>
          </div>
          <button
            onClick={handleRecalculate}
            disabled={recalculating}
            className="rounded-lg border border-ink/20 px-4 py-2 text-sm font-medium hover:bg-ink/5 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {recalculating ? "Recalculating..." : "Recalculate"}
          </button>
        </div>

        {/* Key Statistics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="space-y-1 p-3 rounded-lg bg-ink/5">
            <p className="text-xs font-medium text-ink/70">Sample Size</p>
            <p className="text-2xl font-bold text-ocean">{baseline.sample_size.toLocaleString()}</p>
            <p className="text-xs text-ink/50">cases analyzed</p>
          </div>

          <div className="space-y-1 p-3 rounded-lg bg-ink/5">
            <p className="text-xs font-medium text-ink/70">Adj. Density</p>
            <p className="text-xl font-bold text-sky-600">
              {baseline.density_mean.toFixed(3)}
              <span className="text-sm text-ink/70"> ± {baseline.density_std.toFixed(3)}</span>
            </p>
            <p className="text-xs text-ink/50">mean ± std</p>
          </div>

          <div className="space-y-1 p-3 rounded-lg bg-ink/5">
            <p className="text-xs font-medium text-ink/70">Party Score</p>
            <p className="text-xl font-bold text-sky-600">
              {baseline.party_score_mean.toFixed(3)}
              <span className="text-sm text-ink/70"> ± {baseline.party_score_std.toFixed(3)}</span>
            </p>
            <p className="text-xs text-ink/50">mean ± std</p>
          </div>

          <div className="space-y-1 p-3 rounded-lg bg-ink/5">
            <p className="text-xs font-medium text-ink/70">Last Updated</p>
            <p className="text-xs font-mono">
              {new Date(baseline.calculation_date).toLocaleDateString()}
            </p>
            <p className="text-xs text-ink/50">
              {new Date(baseline.calculation_date).toLocaleTimeString()}
            </p>
          </div>
        </div>

        {/* Chart */}
        <div className="space-y-3 -mx-4 px-4">
          <p className="text-sm font-medium text-ink/70">Feature Distribution</p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 180, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="metric"
                width={170}
                tick={{ fontSize: 12 }}
                interval={0}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#fff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "6px",
                }}
              />
              <Legend wrapperStyle={{ paddingTop: "15px" }} />
              <Bar dataKey="mean" fill="#0ea5e9" name="Mean Value" />
              <Bar dataKey="std" fill="#94e2fc" name="Standard Deviation" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Details Table */}
        <div className="space-y-3">
          <p className="text-sm font-medium text-ink/70">Feature Details</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink/20">
                <th className="text-left py-2 px-3 font-medium text-ink/70">Metric</th>
                <th className="text-right py-2 px-3 font-medium text-ink/70">Mean</th>
                <th className="text-right py-2 px-3 font-medium text-ink/70">Std Dev</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-ink/10">
                <td className="py-2 px-3">Adjournment Density</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.density_mean.toFixed(4)}</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.density_std.toFixed(4)}</td>
              </tr>
              <tr className="border-b border-ink/10">
                <td className="py-2 px-3">Party Driven Score</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.party_score_mean.toFixed(4)}</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.party_score_std.toFixed(4)}</td>
              </tr>
              <tr className="border-b border-ink/10">
                <td className="py-2 px-3">Dormancy CV</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.dormancy_cv_mean.toFixed(4)}</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.dormancy_cv_std.toFixed(4)}</td>
              </tr>
              <tr className="border-b border-ink/10">
                <td className="py-2 px-3">Bench Hunting Index</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.bench_hunting_mean.toFixed(4)}</td>
                <td className="text-right py-2 px-3 font-mono">{baseline.bench_hunting_std.toFixed(4)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Information */}
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-xs font-semibold text-blue-900 mb-1">ℹ️ About Baseline</p>
          <p className="text-xs text-blue-800">
            Population baseline is calculated from {baseline.sample_size.toLocaleString()} cases.
            It serves as the reference point for detecting anomalies. Individual cases with metrics
            significantly different from this baseline are flagged as potential deliberate delay.
          </p>
        </div>
      </div>
    </div>
  );
}
