"use client";

import { useEffect, useState } from "react";

interface CourtPerformance {
  court_id: number;
  court_name: string;
  total_cases: number;
  pending_cases: number;
  disposed_cases: number;
  disposal_rate: number;
  backlog_ratio: number;
}

interface PerformanceResponse {
  courts: CourtPerformance[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function CourtPerformanceTable() {
  const [data, setData] = useState<CourtPerformance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<keyof CourtPerformance>("disposal_rate");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/analytics/courts/performance`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch court performance: ${response.status}`);
        }
        const result = (await response.json()) as PerformanceResponse;
        setData(result.courts);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const handleSort = (key: keyof CourtPerformance) => {
    if (sortBy === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(key);
      setSortAsc(false);
    }
  };

  const sortedData = [...data].sort((a, b) => {
    const aVal = a[sortBy];
    const bVal = b[sortBy];
    const direction = sortAsc ? 1 : -1;

    if (typeof aVal === "number" && typeof bVal === "number") {
      return (aVal - bVal) * direction;
    }
    return 0;
  });

  if (error) {
    return (
      <article className="card">
        <div className="rounded-lg bg-clay/10 p-3 text-sm text-clay">
          Failed to load court performance: {error}
        </div>
      </article>
    );
  }

  if (loading) {
    return (
      <article className="card">
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded bg-ink/10" />
          ))}
        </div>
      </article>
    );
  }

  return (
    <article className="card overflow-hidden">
      <h3 className="mb-4 font-display text-lg">Court Performance Metrics</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink/10">
              <th className="px-4 py-2 text-left text-ink/60">
                <button
                  onClick={() => handleSort("court_name")}
                  className="hover:text-ink"
                >
                  Court {sortBy === "court_name" ? (sortAsc ? "↑" : "↓") : ""}
                </button>
              </th>
              <th className="px-4 py-2 text-right text-ink/60">
                <button
                  onClick={() => handleSort("total_cases")}
                  className="hover:text-ink"
                >
                  Total {sortBy === "total_cases" ? (sortAsc ? "↑" : "↓") : ""}
                </button>
              </th>
              <th className="px-4 py-2 text-right text-ink/60">
                <button
                  onClick={() => handleSort("pending_cases")}
                  className="hover:text-ink"
                >
                  Pending {sortBy === "pending_cases" ? (sortAsc ? "↑" : "↓") : ""}
                </button>
              </th>
              <th className="px-4 py-2 text-right text-ink/60">
                <button
                  onClick={() => handleSort("disposed_cases")}
                  className="hover:text-ink"
                >
                  Disposed {sortBy === "disposed_cases" ? (sortAsc ? "↑" : "↓") : ""}
                </button>
              </th>
              <th className="px-4 py-2 text-right text-ink/60">
                <button
                  onClick={() => handleSort("disposal_rate")}
                  className="hover:text-ink"
                >
                  Disposal Rate {sortBy === "disposal_rate" ? (sortAsc ? "↑" : "↓") : ""}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map((court) => (
              <tr key={court.court_id} className="border-b border-ink/5 hover:bg-ink/5">
                <td className="px-4 py-3 font-medium text-ink">{court.court_name}</td>
                <td className="px-4 py-3 text-right">{court.total_cases.toLocaleString()}</td>
                <td className="px-4 py-3 text-right text-clay">{court.pending_cases.toLocaleString()}</td>
                <td className="px-4 py-3 text-right text-ocean">{court.disposed_cases.toLocaleString()}</td>
                <td className="px-4 py-3 text-right font-medium text-ocean">
                  {formatPercent(court.disposal_rate)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
