"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface CaseTypeData {
  case_type: string;
  case_count: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function CaseTypeChart() {
  const [data, setData] = useState<CaseTypeData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/analytics/cases/by-type`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch case types: ${response.status}`);
        }
        const result = (await response.json()) as CaseTypeData[];
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
      <article className="card">
        <div className="rounded-lg bg-clay/10 p-3 text-sm text-clay">
          Failed to load chart: {error}
        </div>
      </article>
    );
  }

  if (loading) {
    return <article className="card h-80 animate-pulse" />;
  }

  return (
    <article className="card">
      <h3 className="mb-4 font-display text-lg">Cases by Type</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#10151f" opacity={0.1} />
          <XAxis dataKey="case_type" height={60} angle={-45} textAnchor="end" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="case_count" fill="#245e6f" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </article>
  );
}
