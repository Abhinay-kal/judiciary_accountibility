"use client";

import dynamic from "next/dynamic";
import { Suspense, useState } from "react";

const CaseSummaryCard = dynamic(
  () => import("@/components/analytics/CaseSummaryCard").then((module) => module.CaseSummaryCard),
  { ssr: false, loading: () => <div className="card h-40 animate-pulse" /> }
);

const CourtPerformanceTable = dynamic(
  () => import("@/components/analytics/CourtPerformanceTable").then((module) => module.CourtPerformanceTable),
  { ssr: false, loading: () => <div className="card h-96 animate-pulse" /> }
);

const CaseDistributionChart = dynamic(
  () => import("@/components/analytics/CaseDistributionChart").then((module) => module.CaseDistributionChart),
  { ssr: false, loading: () => <div className="card h-80 animate-pulse" /> }
);

const CaseTypeChart = dynamic(
  () => import("@/components/analytics/CaseTypeChart").then((module) => module.CaseTypeChart),
  { ssr: false, loading: () => <div className="card h-80 animate-pulse" /> }
);

const DisposalStatusChart = dynamic(
  () => import("@/components/analytics/DisposalStatusChart").then((module) => module.DisposalStatusChart),
  { ssr: false, loading: () => <div className="card h-80 animate-pulse" /> }
);

const TrendChart = dynamic(
  () => import("@/components/analytics/TrendChart").then((module) => module.TrendChart),
  { ssr: false, loading: () => <div className="card h-96 animate-pulse" /> }
);

const AnalyticsFilter = dynamic(
  () => import("@/components/analytics/AnalyticsFilter").then((module) => module.AnalyticsFilter),
  { ssr: false, loading: () => <div className="card h-20 animate-pulse" /> }
);

type Tab = "overview" | "courts" | "cases" | "trends";

function AnalyticsPageInner() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [filters, setFilters] = useState({
    startDate: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0],
  });

  const tabs: Array<{ key: Tab; label: string }> = [
    { key: "overview", label: "Overview" },
    { key: "courts", label: "Courts" },
    { key: "cases", label: "Cases" },
    { key: "trends", label: "Trends" },
  ];

  const handleFilterChange = (newFilters: typeof filters) => {
    setFilters(newFilters);
  };

  return (
    <div className="route-shell space-y-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Analytics Dashboard</h1>
        <p className="mt-1 text-sm text-ink/60">Comprehensive insights into case statistics and judicial performance</p>
      </div>

      <Suspense fallback={<div className="card h-20 animate-pulse" />}>
        <AnalyticsFilter onChange={handleFilterChange} defaultFilters={filters} />
      </Suspense>

      <div className="flex flex-wrap gap-2 border-b border-ink/10">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-b-2 border-ocean text-ocean"
                : "text-ink/60 hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Suspense fallback={<div className="card h-40 animate-pulse" />}>
              <CaseSummaryCard />
            </Suspense>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Suspense fallback={<div className="card h-80 animate-pulse" />}>
              <CaseDistributionChart />
            </Suspense>
            <Suspense fallback={<div className="card h-80 animate-pulse" />}>
              <DisposalStatusChart />
            </Suspense>
          </div>
        </div>
      )}

      {activeTab === "courts" && (
        <div className="space-y-6">
          <Suspense fallback={<div className="card h-96 animate-pulse" />}>
            <CourtPerformanceTable />
          </Suspense>
        </div>
      )}

      {activeTab === "cases" && (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Suspense fallback={<div className="card h-80 animate-pulse" />}>
              <CaseTypeChart />
            </Suspense>
          </div>
        </div>
      )}

      {activeTab === "trends" && (
        <div className="space-y-6">
          <Suspense fallback={<div className="card h-96 animate-pulse" />}>
            <TrendChart />
          </Suspense>
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense
      fallback={
        <div className="route-shell space-y-6">
          <div className="h-10 w-1/2 animate-pulse rounded-lg bg-ink/10" />
          <div className="grid gap-6">
            <div className="card h-80 animate-pulse" />
          </div>
        </div>
      }
    >
      <AnalyticsPageInner />
    </Suspense>
  );
}
