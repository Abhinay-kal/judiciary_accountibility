"use client";

import { useEffect, useState } from "react";

type DashboardData = {
  timestamp: string;
  active_run: {
    run_id: string;
    status: string;
    started_at: string;
    total_sources: number;
    completed_sources: number;
    successful_sources: number;
    failed_sources: number;
    records_processed: number;
  } | null;
  source_health: {
    healthy: number;
    degraded: number;
    failed: number;
    disabled: number;
    total: number;
  };
  data_counts: {
    cases: number;
    hearings: number;
    judges: number;
  };
  recent_sources: Array<{
    id: number;
    name: string;
    health: string;
    is_active: boolean;
    last_success: string | null;
    last_attempt: string | null;
    failure_count: number;
  }>;
  latest_run: {
    run_id: string;
    status: string;
    started_at: string;
    records_processed: number;
  } | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const getHealthColor = (status: string): string => {
  switch (status) {
    case "HEALTHY":
      return "text-green-600 bg-green-50 border-green-200";
    case "DEGRADED":
      return "text-yellow-600 bg-yellow-50 border-yellow-200";
    case "FAILED":
      return "text-red-600 bg-red-50 border-red-200";
    case "DISABLED":
      return "text-gray-600 bg-gray-50 border-gray-200";
    default:
      return "text-gray-600 bg-gray-50 border-gray-200";
  }
};

const getStatusBadgeColor = (status: string): string => {
  switch (status?.toUpperCase()) {
    case "RUNNING":
      return "bg-blue-100 text-blue-800";
    case "SUCCESS":
      return "bg-green-100 text-green-800";
    case "PARTIAL":
      return "bg-yellow-100 text-yellow-800";
    case "FAILED":
      return "bg-red-100 text-red-800";
    case "QUEUED":
      return "bg-purple-100 text-purple-800";
    case "PENDING":
      return "bg-purple-100 text-purple-800";
    case "COMPLETED":
      return "bg-green-100 text-green-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

export default function AdminDataOverviewPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(new Date());

  async function loadDashboard() {
    try {
      const response = await fetch(`${API_BASE}/admin/data-overview/dashboard`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      setData(payload);
      setError("");
      setLastUpdate(new Date());
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="p-8 text-center">Loading dashboard...</div>;

  return (
    <main className="space-y-6 p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="font-display text-4xl font-bold">Data Overview</h1>
          <p className="text-gray-600 text-sm mt-1">Ingestion statistics and data metrics</p>
        </div>
        <button
          onClick={loadDashboard}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">
          Error: {error}
        </div>
      )}

      {/* Active Run Status */}
      {data?.active_run && (
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 border border-blue-200 rounded-lg p-6 shadow-sm">
          <h2 className="text-xl font-semibold mb-4 text-blue-900">🔄 Active Ingestion Run</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs font-semibold text-blue-700 uppercase">Status</p>
              <span className={`inline-block px-3 py-1 rounded text-sm font-semibold mt-2 ${getStatusBadgeColor(data.active_run.status)}`}>
                {data.active_run.status}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold text-blue-700 uppercase">Progress</p>
              <p className="text-2xl font-bold text-blue-600 mt-2">{data.active_run.completed_sources}/{data.active_run.total_sources}</p>
              <p className="text-xs text-blue-600">sources</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-blue-700 uppercase">Success</p>
              <p className="text-2xl font-bold text-green-600 mt-2">{data.active_run.successful_sources}</p>
              <p className="text-xs text-gray-600">✗ {data.active_run.failed_sources} failed</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-blue-700 uppercase">Records</p>
              <p className="text-2xl font-bold text-blue-600 mt-2">{data.active_run.records_processed.toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition">
          <h3 className="text-sm font-semibold text-gray-600 mb-2">📋 Total Cases</h3>
          <p className="text-4xl font-bold text-blue-600">{data?.data_counts.cases.toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-2">Ingested from all sources</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition">
          <h3 className="text-sm font-semibold text-gray-600 mb-2">👨‍⚖️ Total Hearings</h3>
          <p className="text-4xl font-bold text-purple-600">{data?.data_counts.hearings.toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-2">Court proceedings</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition">
          <h3 className="text-sm font-semibold text-gray-600 mb-2">⚖️ Total Judges</h3>
          <p className="text-4xl font-bold text-green-600">{data?.data_counts.judges.toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-2">Judicial officers</p>
        </div>
      </div>

      {/* Source Health Summary */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">🏥 Source Health Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
            <p className="text-3xl font-bold text-green-600">{data?.source_health.healthy}</p>
            <p className="text-xs font-semibold text-green-700 mt-1">HEALTHY</p>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
            <p className="text-3xl font-bold text-yellow-600">{data?.source_health.degraded}</p>
            <p className="text-xs font-semibold text-yellow-700 mt-1">DEGRADED</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
            <p className="text-3xl font-bold text-red-600">{data?.source_health.failed}</p>
            <p className="text-xs font-semibold text-red-700 mt-1">FAILED</p>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
            <p className="text-3xl font-bold text-gray-600">{data?.source_health.disabled}</p>
            <p className="text-xs font-semibold text-gray-700 mt-1">DISABLED</p>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
            <p className="text-3xl font-bold text-blue-600">{data?.source_health.total}</p>
            <p className="text-xs font-semibold text-blue-700 mt-1">TOTAL</p>
          </div>
        </div>
      </div>

      {/* Recent Sources */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">📊 Recent Sources</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-gray-700 font-semibold">
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last Success</th>
                <th className="px-4 py-3">Active</th>
                <th className="px-4 py-3">Failures</th>
              </tr>
            </thead>
            <tbody>
              {data?.recent_sources.map((src) => (
                <tr key={src.id} className="border-b hover:bg-gray-50 transition">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{src.name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold border ${getHealthColor(src.health)}`}>
                      {src.health}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {src.last_success ? new Date(src.last_success).toLocaleDateString() : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold ${src.is_active ? 'text-green-600' : 'text-gray-400'}`}>
                      {src.is_active ? '✓ Yes' : '✗ No'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs">{src.failure_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Latest Run Summary */}
      {data?.latest_run && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 shadow-sm">
          <h2 className="text-xl font-semibold mb-4">📝 Latest Population Run</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">Status</p>
              <span className={`inline-block px-3 py-1 rounded text-sm font-semibold mt-2 ${getStatusBadgeColor(data.latest_run.status)}`}>
                {data.latest_run.status}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">Started</p>
              <p className="text-sm mt-2 text-gray-700">
                {data.latest_run.started_at ? new Date(data.latest_run.started_at).toLocaleString() : "N/A"}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">Records Processed</p>
              <p className="text-lg font-bold text-blue-600 mt-2">{data.latest_run.records_processed.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">Run ID</p>
              <p className="text-xs font-mono text-gray-700 mt-2">{data.latest_run.run_id.slice(0, 20)}...</p>
            </div>
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 text-right">Last updated: {lastUpdate.toLocaleTimeString()}</p>
    </main>
  );
}
