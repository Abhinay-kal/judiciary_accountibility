"use client";

import { FormEvent, useState } from "react";

type CaseItem = {
  id: number;
  case_number: string;
  status: string;
};

type ResponsePayload = {
  items: CaseItem[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CaseItem[]>([]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const resp = await fetch(`${API_BASE}/cases?court=${encodeURIComponent(query)}&page_size=20`);
    const data: ResponsePayload = await resp.json();
    setResults(data.items ?? []);
  }

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Search Cases</h1>
      <p className="text-sm text-ink/70">Search by case number or party name via API filters.</p>
      <form onSubmit={onSubmit} className="card flex gap-2">
        <input
          className="w-full rounded-lg border border-ink/20 bg-white p-3"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter case number, court, or party keyword"
        />
        <button className="rounded-lg bg-ocean px-4 py-2 text-white" type="submit">
          Search
        </button>
      </form>

      <ul className="space-y-2">
        {results.map((item) => (
          <li key={item.id} className="card">
            <p className="font-semibold">{item.case_number}</p>
            <p className="text-sm text-ink/70">Status: {item.status}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
