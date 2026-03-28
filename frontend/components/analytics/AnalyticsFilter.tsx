"use client";

import { useState } from "react";

interface Filters {
  startDate: string;
  endDate: string;
}

interface Props {
  onChange: (filters: Filters) => void;
  defaultFilters: Filters;
}

export function AnalyticsFilter({ onChange, defaultFilters }: Props) {
  const [filters, setFilters] = useState<Filters>(defaultFilters);

  const handleChange = (key: keyof Filters, value: string) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    onChange(newFilters);
  };

  return (
    <article className="card">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:gap-6">
        <div>
          <label className="block text-sm font-medium text-ink/60 mb-2">
            Start Date
          </label>
          <input
            type="date"
            value={filters.startDate}
            onChange={(e) => handleChange("startDate", e.target.value)}
            className="rounded border border-ink/20 bg-white px-3 py-2 text-sm text-ink placeholder-ink/40 focus:border-ocean focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink/60 mb-2">
            End Date
          </label>
          <input
            type="date"
            value={filters.endDate}
            onChange={(e) => handleChange("endDate", e.target.value)}
            className="rounded border border-ink/20 bg-white px-3 py-2 text-sm text-ink placeholder-ink/40 focus:border-ocean focus:outline-none"
          />
        </div>
        <button
          onClick={() => {
            const now = new Date();
            const oneYearAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
            const newFilters = {
              startDate: oneYearAgo.toISOString().split('T')[0],
              endDate: now.toISOString().split('T')[0],
            };
            setFilters(newFilters);
            onChange(newFilters);
          }}
          className="rounded bg-ocean px-4 py-2 text-sm font-medium text-white hover:bg-ocean/80 transition-colors"
        >
          Last 12 Months
        </button>
      </div>
    </article>
  );
}
