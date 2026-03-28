"use client";

import { useState } from "react";
import dynamic from "next/dynamic";

const CaseDelaySearch = dynamic(
  () => import("@/components/CaseDelaySearch").then((module) => module.CaseDelaySearch),
  { ssr: false, loading: () => <div className="h-64 bg-ink/10 rounded-lg animate-pulse" /> }
);

const BaselineMetrics = dynamic(
  () => import("@/components/BaselineMetrics").then((module) => module.BaselineMetrics),
  { ssr: false, loading: () => <div className="h-64 bg-ink/10 rounded-lg animate-pulse" /> }
);

const BatchDelayAnalysis = dynamic(
  () => import("@/components/BatchDelayAnalysis").then((module) => module.BatchDelayAnalysis),
  { ssr: false, loading: () => <div className="h-64 bg-ink/10 rounded-lg animate-pulse" /> }
);

type TabKey = "overview" | "single" | "batch" | "baseline";

const TABS: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: "overview", label: "Overview", icon: "📊" },
  { key: "single", label: "Single Case", icon: "🔍" },
  { key: "batch", label: "Batch Analysis", icon: "📈" },
  { key: "baseline", label: "Population Baseline", icon: "📐" },
];

export default function DelayDetectionPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="font-display text-3xl">Deliberate Delay Detection</h1>
        <p className="text-ink/70">
          Analyze cases for patterns of deliberate delay using machine learning-powered detection.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg font-medium transition whitespace-nowrap ${
              activeTab === tab.key
                ? "bg-ocean text-white"
                : "bg-ink/10 text-ink/70 hover:bg-ink/20"
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div>{renderTabContent(activeTab)}</div>

      {/* Info */}
      <div className="card space-y-3">
        <p className="text-sm font-medium text-ink/70">How It Works</p>
        <ol className="space-y-2 text-sm text-ink/60">
          <li className="flex gap-3">
            <span className="font-bold text-ocean">1</span>
            <span>
              <strong className="text-ink/90">Phase 1:</strong> Classify adjournment tactics (proxy counsel,
              frivolous filings, judge unavailability, etc.)
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold text-ocean">2</span>
            <span>
              <strong className="text-ink/90">Phase 2:</strong> Extract 4 key features from case data
              (adjournment density, party-driven score, dormancy, bench hunting)
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold text-ocean">3</span>
            <span>
              <strong className="text-ink/90">Phase 3:</strong> Compare metrics against population baseline
              using Z-scores to calculate deliberate delay probability (0-100%)
            </span>
          </li>
        </ol>
      </div>

      {/* Technical Details */}
      <div className="card space-y-3">
        <p className="text-sm font-medium text-ink/70">Risk Levels</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div className="p-3 rounded-lg bg-green-50 border border-green-200">
            <p className="font-semibold text-green-900">Low</p>
            <p className="text-xs text-green-700">0-25% probability</p>
          </div>
          <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
            <p className="font-semibold text-yellow-900">Moderate</p>
            <p className="text-xs text-yellow-700">25-50% probability</p>
          </div>
          <div className="p-3 rounded-lg bg-orange-50 border border-orange-200">
            <p className="font-semibold text-orange-900">High</p>
            <p className="text-xs text-orange-700">50-75% probability</p>
          </div>
          <div className="p-3 rounded-lg bg-red-50 border border-red-200">
            <p className="font-semibold text-red-900">Extreme</p>
            <p className="text-xs text-red-700">75-100% probability</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function renderTabContent(tab: TabKey) {
  switch (tab) {
    case "overview":
      return <OverviewTab />;
    case "single":
      return <CaseDelaySearch />;
    case "batch":
      return <BatchDelayAnalysis />;
    case "baseline":
      return <BaselineMetrics />;
  }
}

function OverviewTab() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <QuickStartCard
        title="Analyze Single Case"
        description="Enter a case ID to perform detailed delay detection analysis"
        action="Go to Single Case"
        href="#single"
        icon="🔍"
      />
      <QuickStartCard
        title="Batch Analysis"
        description="Analyze up to 1,000 cases at once and get summary statistics"
        action="Go to Batch Analysis"
        href="#batch"
        icon="📈"
      />
      <QuickStartCard
        title="Population Baseline"
        description="View population-wide metrics used for anomaly detection"
        action="View Baseline"
        href="#baseline"
        icon="📐"
      />
      <QuickStartCard
        title="API Documentation"
        description="Access the REST API endpoints for programmatic access"
        action="Read API Docs"
        href="http://localhost:8000/docs"
        external
        icon="📚"
      />
    </div>
  );
}

interface QuickStartCardProps {
  title: string;
  description: string;
  action: string;
  href: string;
  icon: string;
  external?: boolean;
}

function QuickStartCard({ title, description, action, href, icon, external }: QuickStartCardProps) {
  const LinkComponent = external ? "a" : "button";

  return (
    <div className="card space-y-4">
      <div className="flex items-start gap-3">
        <span className="text-3xl">{icon}</span>
        <div className="flex-1">
          <h3 className="font-semibold text-lg">{title}</h3>
          <p className="text-sm text-ink/70">{description}</p>
        </div>
      </div>
      {external ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block text-sm font-medium text-ocean hover:underline"
        >
          {action} →
        </a>
      ) : (
        <button className="text-sm font-medium text-ocean hover:underline">
          {action} →
        </button>
      )}
    </div>
  );
}
