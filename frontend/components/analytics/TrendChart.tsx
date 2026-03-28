"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface TrendData {
  month: string;
  cases_filed: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function TrendChart() {
  const [data, setData] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/analytics/cases/trend/12-months`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch trend: ${response.status}`);
        }
        interface TrendResponse {
          months: string[];
          data: number[];
        }
        const result = (await response.json()) as TrendResponse;
        if (result.months && result.data && Array.isArray(result.months) && Array.isArray(result.data)) {
          const chartData = result.data.map((count: number, idx: number) => ({
            month: result.months[idx] || `Month ${idx + 1}`,
            cases_filed: count,
          }));
          setData(chartData);
        } else {
          setData([]);
        }
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
    return <article className="card h-96 animate-pulse" />;
  }

  if (data.length === 0) {
    return (
      <article className="card">
        <h3 className="mb-4 font-display text-lg">12-Month Case Filing Trend</h3>
        <div className="text-center text-ink/40 py-12">No data available</div>
      </article>
    );
  }

  return (
    <article className="card">
      <h3 className="mb-4 font-display text-lg">12-Month Case Filing Trend</h3>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#10151f" opacity={0.1} />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="cases_filed"
            stroke="#245e6f"
            dot={{ fill: "#d1764f", r: 4 }}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </article>
  );
}
