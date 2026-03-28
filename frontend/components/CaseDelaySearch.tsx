"use client";

import { FormEvent, useState } from "react";
import dynamic from "next/dynamic";

const DelayDetectionAnalysis = dynamic(
  () => import("./DelayDetectionAnalysis").then((module) => module.DelayDetectionAnalysis),
  {
    ssr: false,
    loading: () => <div className="h-64 bg-ink/10 rounded-lg animate-pulse" />,
  }
);

export function CaseDelaySearch() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();

    // Try parsing as case ID number
    const caseId = parseInt(searchQuery.trim());

    if (isNaN(caseId) || caseId <= 0) {
      setError("Please enter a valid case ID (numeric)");
      return;
    }

    setLoading(true);
    setError(null);

    // In a real app, you might verify the case exists first
    // For now, we'll pass the ID directly to the analysis component
    setSelectedCaseId(caseId);
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      {/* Search Form */}
      <div className="card">
        <h3 className="font-semibold text-lg mb-4">Search Case for Delay Analysis</h3>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="number"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setError(null);
            }}
            placeholder="Enter case ID"
            className="flex-1 rounded-lg border border-ink/20 bg-white p-3"
            disabled={loading}
            min="1"
          />
          <button
            type="submit"
            disabled={loading || !searchQuery.trim()}
            className="rounded-lg bg-ocean px-6 py-3 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-ocean/90 transition"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-900">{error}</p>
          </div>
        )}

        {/* Example text */}
        <p className="text-xs text-ink/50 mt-3">
          💡 Enter a numeric case ID to perform delay detection analysis. Results show probability,
          risk level, and feature breakdown.
        </p>
      </div>

      {/* Analysis Results */}
      {selectedCaseId && <DelayDetectionAnalysis caseId={selectedCaseId} />}
    </div>
  );
}
