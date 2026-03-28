"use client";

import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from "recharts";

interface DistributionItem {
  court_name?: string;
  state?: string;
  case_count?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const COLORS = ["#245e6f", "#d1764f", "#a8d7cd", "#f4e7cf", "#10151f"];

interface Props {
  groupBy?: "court" | "state";
}

export function CaseDistributionChart({ groupBy = "court" }: Props) {
  const [data, setData] = useState<Array<{ name: string; value: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const endpoint = groupBy === "court" ? "by-court" : "by-state";
        const response = await fetch(`${API_BASE}/analytics/cases/${endpoint}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch distribution: ${response.status}`);
        }
        const result = (await response.json()) as DistributionItem[];
        const items = result.map((item) => ({
          name: groupBy === "court" ? (item.court_name || "Unknown") : (item.state || "Unknown"),
          value: item.case_count || 0,
        }));
        setData(items);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [groupBy]);

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
      <h3 className="mb-4 font-display text-lg">
        Cases by {groupBy === "court" ? "Court" : "State"}
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, value }) => `${name}: ${value}`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </article>
  );
}
