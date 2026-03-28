"use client";

import { useEffect, useState } from "react";
import { StatCard } from "@/components/StatCard";

interface SummaryData {
  total_cases: number;
  pending_cases: number;
  disposed_cases: number;
  disposal_rate: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function CaseSummaryCard() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/analytics/cases/summary`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch summary: ${response.status}`);
        }
        const result = (await response.json()) as SummaryData;
        setData(result);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (error) {
    return (
      <div className="card bg-clay/10 p-4 text-sm text-clay">
        Failed to load summary: {error}
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="grid gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="card h-40 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <>
      <StatCard
        label="Total Cases"
        value={data.total_cases.toLocaleString()}
      />
      <StatCard
        label="Pending Cases"
        value={data.pending_cases.toLocaleString()}
      />
      <StatCard
        label="Disposed Cases"
        value={data.disposed_cases.toLocaleString()}
      />
      <StatCard
        label="Disposal Rate"
        value={`${(data.disposal_rate * 100).toFixed(1)}%`}
      />
    </>
  );
}
