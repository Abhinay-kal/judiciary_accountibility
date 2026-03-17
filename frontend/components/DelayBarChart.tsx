"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Item = { court: string; pending: number };

export function DelayBarChart({ data }: { data: Item[] }) {
  return (
    <div className="card h-80">
      <h3 className="font-display text-lg">Top Delayed Courts</h3>
      <ResponsiveContainer width="100%" height="90%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="court" hide />
          <YAxis />
          <Tooltip />
          <Bar dataKey="pending" fill="#245e6f" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
