"use client";

import { useEffect, useState } from "react";

interface CourtPerformance {
  court_id: number;
  court_name: string;
  total_cases: number;
  disposed_cases: number;
  pending_cases: number;
  disposal_rate: number;
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
  const [sortBy, setSortBy] = useState<"court_name" | "total_cases" | "disposal_rate">("disposal_rate");
  const [sortAsc, setSortAsc] = useState(false);

  const getSortIcon = (key: string): string => {
    if (sortBy !== key) return "";
    return sortAsc ? "↑" : "↓";
  };

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
        setData(result.courts || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setData([]);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const handleSort = (key: "court_name" | "total_cases" | "disposal_rate") => {
    if (sortBy === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(key);
      setSortAsc(false);
    }
  };

  const sortedData = [...data].sort((a, b) => {
    let aVal: number | string = "";
    let bVal: number | string = "";

    switch (sortBy) {
      case "court_name":
        aVal = a.court_name;
        bVal = b.court_name;
        break;
      case "total_cases":
        aVal = a.total_cases ?? 0;
        bVal = b.total_cases ?? 0;
        break;
      case "disposal_rate":
        aVal = a.disposal_rate ?? 0;
        bVal = b.disposal_rate ?? 0;
        break;
    }

    const direction = sortAsc ? 1 : -1;

    if (typeof aVal === "number" && typeof bVal === "number") {
      return (aVal - bVal) * direction;
    }

    if (typeof aVal === "string" && typeof bVal === "string") {
      return aVal.localeCompare(bVal) * direction;
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
                  Court {getSortIcon("court_name")}
                </button>
              </th>
              <th className="px-4 py-2 text-right text-ink/60">
                <button
                  onClick={() => handleSort("total_cases")}
                  className="hover:text-ink"
                >
                  Total Cases {getSortIcon("total_cases")}
                </button>
              </th>
              <th className="px-4 py-2 text-right text-ink/60">
                <button
                  onClick={() => handleSort("disposal_rate")}
                  className="hover:text-ink"
                >
                  Disposal Rate {getSortIcon("disposal_rate")}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map((court) => (
              <tr key={court.court_id} className="border-b border-ink/5 hover:bg-ink/5">
                <td className="px-4 py-3 font-medium text-ink">{court.court_name}</td>
                <td className="px-4 py-3 text-right">{(court.total_cases ?? 0).toLocaleString()}</td>
                <td className="px-4 py-3 text-right">{(court.disposal_rate ?? 0).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.length === 0 && !loading && !error && (
        <div className="p-4 text-center text-ink/60">
          No court performance data available
        </div>
      )}
    </article>
  );
}
