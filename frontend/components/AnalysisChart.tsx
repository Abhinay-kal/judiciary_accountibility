"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface CaseFeatures {
  case_id: number;
  case_number: string;
  adjournment_density: number;
  party_driven_score: number;
  dormancy_cv: number;
  bench_hunting_index: number;
}

interface AnalysisChartProps {
  features: CaseFeatures;
  probability: number;
}

export function AnalysisChart({ features, probability }: AnalysisChartProps) {
  // Prepare data for the chart
  const data = [
    {
      name: "Adjournment\nDensity",
      value: Math.min(features.adjournment_density * 100, 100),
      baseline: 50,
    },
    {
      name: "Party Driven\nScore",
      value: features.party_driven_score * 100,
      baseline: 50,
    },
    {
      name: "Dormancy\nCV",
      value: Math.min(features.dormancy_cv * 100, 100),
      baseline: 50,
    },
    {
      name: "Bench Hunting\nIndex",
      value: Math.min(features.bench_hunting_index * 100, 100),
      baseline: 50,
    },
    {
      name: "Delay\nProbability",
      value: probability,
      baseline: 35, // Average expected probability
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-medium text-ink/70 mb-2">Feature Analysis</p>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="name"
              angle={-45}
              textAnchor="end"
              height={80}
              tick={{ fontSize: 12, fill: "#666" }}
            />
            <YAxis
              label={{ value: "Normalized Score (0-100)", angle: -90, position: "insideLeft" }}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fff",
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
              }}
              formatter={(value: number) => value.toFixed(2)}
            />
            <Bar dataKey="value" fill="#0ea5e9" name="Observed" radius={[6, 6, 0, 0]} />
            <Bar dataKey="baseline" fill="#e5e7eb" name="Baseline Avg" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Feature Insights */}
      <div className="space-y-2 text-sm">
        <p className="font-medium text-ink/70">Feature Insights</p>
        <ul className="space-y-1 text-ink/60">
          <li className="flex items-start gap-2">
            <span className="text-blue-500 mt-1">•</span>
            <span>
              <strong>Adjournment Density:</strong> {features.adjournment_density.toFixed(3)} - Frequency
              of adjournments relative to case age
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 mt-1">•</span>
            <span>
              <strong>Party Driven Score:</strong> {features.party_driven_score.toFixed(3)} - Proportion
              of adjournments requested by counsel
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 mt-1">•</span>
            <span>
              <strong>Dormancy CV:</strong> {features.dormancy_cv.toFixed(3)} - Variability in inactive
              periods between hearings
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 mt-1">•</span>
            <span>
              <strong>Bench Hunting Index:</strong> {features.bench_hunting_index.toFixed(3)} - Pattern of
              reassignments to different benches
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}
