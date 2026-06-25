"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { Route } from "next";
import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

const AdminCorrectionQueue = dynamic(
  () => import("@/components/AdminCorrectionQueue").then((module) => module.AdminCorrectionQueue),
  { ssr: false, loading: () => <p className="text-sm text-ink/70">Loading correction queue...</p> }
);

const CorrectionRequestForm = dynamic(
  () => import("@/components/CorrectionRequestForm").then((module) => module.CorrectionRequestForm),
  { ssr: false, loading: () => <p className="text-sm text-ink/70">Loading correction form...</p> }
);

const DelayBarChart = dynamic(
  () => import("@/components/DelayBarChart").then((module) => module.DelayBarChart),
  { ssr: false, loading: () => <p className="text-sm text-ink/70">Loading chart...</p> }
);

const CaseDelaySearch = dynamic(
  () => import("@/components/CaseDelaySearch").then((module) => module.CaseDelaySearch),
  { ssr: false, loading: () => <p className="text-sm text-ink/70">Loading delay detection...</p> }
);

const BaselineMetrics = dynamic(
  () => import("@/components/BaselineMetrics").then((module) => module.BaselineMetrics),
  { ssr: false, loading: () => <p className="text-sm text-ink/70">Loading baseline...</p> }
);

const BatchDelayAnalysis = dynamic(
  () => import("@/components/BatchDelayAnalysis").then((module) => module.BatchDelayAnalysis),
  { ssr: false, loading: () => <p className="text-sm text-ink/70">Loading batch analysis...</p> }
);

type HubSectionKey =
  | "overview"
  | "search"
  | "judges"
  | "heatmap"
  | "open_data"
  | "corrections"
  | "feedback"
  | "population"
  | "delay_detection"
  | "analytics";

type CourtStat = {
  court_id: number;
  court_name: string;
  total_cases: number;
  pending_cases: number;
  disposed_cases: number;
  backlog_ratio: number;
};

type FlagItem = {
  id: number;
  case_id: number;
  flag_type: string;
  details?: { summary?: string };
};

type CaseItem = {
  id: number;
  case_number: string;
  status: string;
};

type JudgeItem = {
  id: number;
  name: string;
};

type JudgeStats = {
  judge_id: number;
  judge_name: string;
  total_hearings: number;
  adjournment_rate: number;
  median_disposal_days: number;
};

type DatasetItem = {
  dataset_id: string;
  name: string;
  description: string;
  version: string;
};

type PendingFeedbackItem = {
  id: string;
  case_id: number;
  responder_name: string;
  responder_affiliation?: string;
  responder_contact: string;
  submitted_at: string;
};

type PopulationRunItem = {
  run_id: string;
  status: string;
  trigger_type: string;
  completed_sources: number;
  total_sources: number;
  records_processed: number;
  records_failed: number;
  started_at: string;
};

type PopulationSourceItem = {
  id: number;
  source_name: string;
  status: string;
  records_processed: number;
  records_failed: number;
  error_summary?: string | null;
};

type PopulationRunDetail = {
  run: PopulationRunItem;
  sources: PopulationSourceItem[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";
const BACKEND_DOCS_URL = `${API_BASE.replace(/\/api\/v1\/?$/, "")}/docs`;
const ACTIVE_STATUSES = new Set(["QUEUED", "RUNNING"]);

const SECTIONS: Array<{ key: HubSectionKey; label: string; helper: string }> = [
  { key: "overview", label: "Overview", helper: "Core health and flagged activity" },
  { key: "search", label: "Case Search", helper: "Find cases fast" },
  { key: "judges", label: "Judges", helper: "Judge list and performance stats" },
  { key: "heatmap", label: "Heatmap", helper: "Backlog intensity by court" },
  { key: "analytics", label: "Analytics", helper: "Comprehensive case and court analytics" },
  { key: "open_data", label: "Open Data", helper: "Catalog and download links" },
  { key: "delay_detection", label: "Delay Detection", helper: "Deliberate delay analysis" },
  { key: "corrections", label: "Corrections", helper: "Submit and moderate requests" },
  { key: "feedback", label: "RtR Feedback", helper: "Moderate official responses" },
  { key: "population", label: "Population", helper: "Run and monitor full ingestion" },
];

const SECTION_KEY_SET = new Set<HubSectionKey>(SECTIONS.map((item) => item.key));

function asSection(value: string | null): HubSectionKey {
  if (value && SECTION_KEY_SET.has(value as HubSectionKey)) {
    return value as HubSectionKey;
  }
  return "overview";
}

function fmtPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fmtDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function SectionSkeleton({ rows = 3 }: Readonly<{ rows?: number }>) {
  return (
    <div className="card animate-pulse space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={`skeleton-${index}`} className="h-10 rounded-lg bg-ink/10" />
      ))}
    </div>
  );
}

function UnifiedHubInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [section, setSection] = useState<HubSectionKey>(() => asSection(searchParams.get("section")));
  const [mountedSections, setMountedSections] = useState<Set<HubSectionKey>>(() => new Set([asSection(searchParams.get("section"))]));
  const [message, setMessage] = useState("");
  const [showSectionMenu, setShowSectionMenu] = useState(false);

  const [courtStats, setCourtStats] = useState<CourtStat[]>([]);
  const [flags, setFlags] = useState<FlagItem[]>([]);
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);

  const [searchQuery, setSearchQuery] = useState(() => searchParams.get("q") ?? "");
  const [searchResults, setSearchResults] = useState<CaseItem[]>([]);
  const [isLoadingSearch, setIsLoadingSearch] = useState(false);

  const [judges, setJudges] = useState<JudgeItem[]>([]);
  const [selectedJudgeId, setSelectedJudgeId] = useState<number | null>(() => {
    const value = searchParams.get("judge_id");
    if (!value) {
      return null;
    }
    const numeric = Number(value);
    return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
  });
  const [judgeStats, setJudgeStats] = useState<JudgeStats | null>(null);
  const [isLoadingJudgeStats, setIsLoadingJudgeStats] = useState(false);

  const [correctionTargetType, setCorrectionTargetType] = useState<"case" | "flag" | "evidence" | "hearing">(() => {
    const value = searchParams.get("target_type");
    return value === "flag" || value === "evidence" || value === "hearing" ? value : "case";
  });
  const [correctionTargetId, setCorrectionTargetId] = useState<number>(() => {
    const value = searchParams.get("target_id");
    if (!value) {
      return 1;
    }
    const numeric = Number(value);
    return Number.isInteger(numeric) && numeric > 0 ? numeric : 1;
  });

  const [feedbackAdminId, setFeedbackAdminId] = useState("1");
  const [feedbackRows, setFeedbackRows] = useState<PendingFeedbackItem[]>([]);
  const [isLoadingFeedback, setIsLoadingFeedback] = useState(false);

  const [populationAdminId, setPopulationAdminId] = useState("1");
  const [populationReason, setPopulationReason] = useState("Unified hub manual population run");
  const [populationRuns, setPopulationRuns] = useState<PopulationRunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(() => searchParams.get("run_id"));
  const [populationDetail, setPopulationDetail] = useState<PopulationRunDetail | null>(null);
  const [isLoadingPopulation, setIsLoadingPopulation] = useState(false);
  const [isLoadingPopulationDetail, setIsLoadingPopulationDetail] = useState(false);
  const [isTriggeringPopulation, setIsTriggeringPopulation] = useState(false);
  const [isLoadingPublic, setIsLoadingPublic] = useState(false);

  const inFlightRequests = useRef<Map<string, Promise<unknown>>>(new Map());
  const publicDataLoaded = useRef(false);
  const feedbackLoaded = useRef(false);
  const populationLoaded = useRef(false);
  const lastRestoredSearch = useRef<string>("");

  const hasActivePopulationRun = useMemo(
    () => populationRuns.some((run) => ACTIVE_STATUSES.has(run.status)),
    [populationRuns]
  );

  const populationButtonText = useMemo(() => {
    if (hasActivePopulationRun) return "Run in progress";
    if (isTriggeringPopulation) return "Queueing...";
    return "Start population";
  }, [hasActivePopulationRun, isTriggeringPopulation]);

  const totalCases = useMemo(() => courtStats.reduce((sum, item) => sum + item.total_cases, 0), [courtStats]);
  const pendingCases = useMemo(() => courtStats.reduce((sum, item) => sum + item.pending_cases, 0), [courtStats]);
  const disposedCases = useMemo(() => courtStats.reduce((sum, item) => sum + item.disposed_cases, 0), [courtStats]);

  const updateQueryParams = useCallback(
    (entries: Record<string, string | null>) => {
      const params = new URLSearchParams(globalThis.location.search);
      for (const [key, value] of Object.entries(entries)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }

      const query = params.toString();
      const nextUrl = query ? `${pathname}?${query}` : pathname;
      const currentUrl = `${globalThis.location.pathname}${globalThis.location.search}`;
      if (nextUrl === currentUrl) {
        return;
      }
      globalThis.history.replaceState(null, "", nextUrl);
    },
    [pathname]
  );

  const fetchJsonDedup = useCallback(
    async function fetchJsonDedupInner<T>(key: string, url: string): Promise<T> {
      const existing = inFlightRequests.current.get(key);
      if (existing) {
        return existing as Promise<T>;
      }

      const pending = (async () => {
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Request failed for ${key}`);
        }
        return (await response.json()) as T;
      })();

      inFlightRequests.current.set(key, pending as Promise<unknown>);
      try {
        return await pending;
      } finally {
        inFlightRequests.current.delete(key);
      }
    },
    []
  );

  const loadPublicOverview = useCallback(async () => {
    setIsLoadingPublic(true);
    try {
      const [statsPayload, flagsPayload, datasetsPayload, judgesPayload] = await Promise.all([
        fetchJsonDedup<CourtStat[]>("stats.court", `${API_BASE}/stats/court`).catch(() => []),
        fetchJsonDedup<{ items: FlagItem[] }>("flags.first_page", `${API_BASE}/flags?page=1&page_size=8`).catch(() => ({ items: [] })),
        fetchJsonDedup<{ items: DatasetItem[] }>("datasets.catalog", `${API_BASE}/datasets`).catch(() => ({ items: [] })),
        fetchJsonDedup<JudgeItem[]>("judges.all", `${API_BASE}/judges`).catch(() => []),
      ]);

      setCourtStats(Array.isArray(statsPayload) ? statsPayload : []);
      setFlags(Array.isArray(flagsPayload.items) ? flagsPayload.items : []);
      setDatasets(Array.isArray(datasetsPayload.items) ? datasetsPayload.items : []);
      setJudges(Array.isArray(judgesPayload) ? judgesPayload : []);
    } catch {
      setMessage("Failed to load overview data.");
    } finally {
      setIsLoadingPublic(false);
    }
  }, [fetchJsonDedup]);

  const loadFeedback = useCallback(async () => {
    setIsLoadingFeedback(true);
    const payload = await fetchJsonDedup<{ items: PendingFeedbackItem[] }>(
      "feedback.pending",
      `${API_BASE}/admin/feedback/pending`
    ).catch(() => ({ items: [] }));
    setFeedbackRows(payload.items || []);
    setIsLoadingFeedback(false);
  }, [fetchJsonDedup]);

  const loadPopulationRuns = useCallback(async () => {
    setIsLoadingPopulation(true);
    const payload = await fetchJsonDedup<{ items: PopulationRunItem[] }>(
      "population.runs",
      `${API_BASE}/admin/population/runs?limit=20&offset=0`
    ).catch(() => ({ items: [] }));
    const runs = payload.items || [];
    setPopulationRuns(runs);
    if (runs.length > 0) {
      const firstRun = runs[0].run_id;
      setSelectedRunId((previous) => previous ?? firstRun);
    }
    setIsLoadingPopulation(false);
  }, [fetchJsonDedup]);

  const loadPopulationDetail = useCallback(async (runId: string) => {
    setIsLoadingPopulationDetail(true);
    const payload = await fetchJsonDedup<PopulationRunDetail>(
      `population.detail.${runId}`,
      `${API_BASE}/admin/population/runs/${runId}`
    ).catch(() => null);
    if (!payload) {
      setMessage(`Failed to load run details for ${runId}`);
      setIsLoadingPopulationDetail(false);
      return;
    }
    setPopulationDetail(payload);
    setIsLoadingPopulationDetail(false);
  }, [fetchJsonDedup]);

  const runSearch = useCallback(async (query: string, syncUrl: boolean) => {
    const normalized = query.trim();
    if (!normalized) {
      setSearchResults([]);
      if (syncUrl) {
        updateQueryParams({ q: null });
      }
      return;
    }
    setIsLoadingSearch(true);
    const payload = await fetchJsonDedup<{ items: CaseItem[] }>(
      `cases.search.${normalized}`,
      `${API_BASE}/cases?court=${encodeURIComponent(normalized)}&page_size=20`
    ).catch(() => ({ items: [] }));
    setSearchResults(payload.items || []);
    setIsLoadingSearch(false);
    if (syncUrl) {
      updateQueryParams({ q: normalized });
    }
  }, [fetchJsonDedup, updateQueryParams]);

  useEffect(() => {
    if (section !== "search") {
      return;
    }
    const restoredQuery = (searchParams.get("q") ?? "").trim();
    if (!restoredQuery || restoredQuery === lastRestoredSearch.current) {
      return;
    }
    lastRestoredSearch.current = restoredQuery;
    runSearch(restoredQuery, false);
  }, [section, searchParams, runSearch]);

  useEffect(() => {
    const needsPublicData = section === "overview" || section === "judges" || section === "heatmap" || section === "open_data" || section === "analytics";
    if (needsPublicData && !publicDataLoaded.current) {
      publicDataLoaded.current = true;
      loadPublicOverview();
    }
    if (section === "feedback" && !feedbackLoaded.current) {
      feedbackLoaded.current = true;
      loadFeedback();
    }
    if (section === "population" && !populationLoaded.current) {
      populationLoaded.current = true;
      loadPopulationRuns();
    }
  }, [section, loadFeedback, loadPopulationRuns, loadPublicOverview]);

  useEffect(() => {
    setMountedSections((previous) => {
      if (previous.has(section)) {
        return previous;
      }
      const next = new Set(previous);
      next.add(section);
      return next;
    });
  }, [section]);

  useEffect(() => {
    if (!selectedJudgeId) {
      setJudgeStats(null);
      return;
    }
    async function loadJudgeStats() {
      setIsLoadingJudgeStats(true);
      const payload = await fetchJsonDedup<JudgeStats>(
        `judges.stats.${selectedJudgeId}`,
        `${API_BASE}/judges/${selectedJudgeId}/stats`
      ).catch(() => null);
      if (payload) {
        setJudgeStats(payload);
      }
      setIsLoadingJudgeStats(false);
    }
    loadJudgeStats();
  }, [selectedJudgeId, fetchJsonDedup]);

  useEffect(() => {
    if (!selectedRunId) {
      setPopulationDetail(null);
      return;
    }
    loadPopulationDetail(selectedRunId);
  }, [selectedRunId, loadPopulationDetail]);

  useEffect(() => {
    if (section !== "population") {
      return;
    }
    const poller = setInterval(() => {
      loadPopulationRuns();
      if (selectedRunId) {
        loadPopulationDetail(selectedRunId);
      }
    }, hasActivePopulationRun ? 5000 : 15000);

    return () => clearInterval(poller);
  }, [section, hasActivePopulationRun, selectedRunId, loadPopulationRuns, loadPopulationDetail]);

  useEffect(() => {
    updateQueryParams({
      section,
      judge_id: selectedJudgeId ? String(selectedJudgeId) : null,
      target_type: correctionTargetType,
      target_id: String(correctionTargetId),
      run_id: selectedRunId || null,
    });
  }, [section, selectedJudgeId, correctionTargetType, correctionTargetId, selectedRunId, updateQueryParams]);

  async function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runSearch(searchQuery, true);
  }

  async function feedbackAction(
    id: string,
    action: "verify" | "publish" | "reject" | "limit" | "escalate"
  ) {
    const body: Record<string, unknown> = { admin_id: Number(feedbackAdminId) };
    if (action === "verify") {
      body.method = "admin_verified";
      body.reason = "Manual directory validation";
    }
    if (action === "publish") {
      body.public_note = "An official response was submitted and verified.";
    }
    if (action === "reject") {
      body.reason = "Insufficient verification evidence";
    }
    if (action === "limit") {
      body.reason = "PII redacted";
      body.public_note = "Response published in limited form after redaction.";
      body.redacted_content = "Redacted by moderation team.";
    }
    if (action === "escalate") {
      body.reason = "Escalated for legal review";
    }

    const response = await fetch(`${API_BASE}/admin/feedback/${id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      setMessage(`Feedback action ${action} failed for ${id}`);
      return;
    }
    setMessage(`Feedback action ${action} completed for ${id}`);
    loadFeedback();
  }

  async function triggerPopulationRun() {
    setIsTriggeringPopulation(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/admin/population/runs/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          admin_id: Number(populationAdminId),
          reason: populationReason,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setMessage(payload.detail || "Failed to trigger population run");
        return;
      }
      setMessage(payload.status === "already_running" ? `Run already active: ${payload.run_id}` : `Run queued: ${payload.run_id}`);
      await loadPopulationRuns();
      if (payload.run_id) {
        setSelectedRunId(payload.run_id);
      }
    } finally {
      setIsTriggeringPopulation(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Header Section */}
      <header className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-1">
          <p className="text-xs font-semibold tracking-widest text-ocean/70 uppercase">Sustainable Data</p>
          <h1 className="font-display text-5xl font-bold text-ink">Unified Operations Hub</h1>
        </div>
        <div className="flex gap-2 pt-2">
          <Link
            href="/analytics"
            className="text-xs font-semibold text-ocean hover:underline whitespace-nowrap"
          >
            View Analytics →
          </Link>
          <button
            onClick={() => setShowSectionMenu(!showSectionMenu)}
            className="text-2xl hover:opacity-70 transition-opacity"
            title="Toggle navigation menu"
          >
            ☰
          </button>
        </div>
      </header>

      {/* Section Navigation Drawer */}
      {showSectionMenu && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm" onClick={() => setShowSectionMenu(false)}>
          <div className="fixed inset-y-0 left-0 w-64 bg-white shadow-xl overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between gap-4 mb-6">
                <h2 className="font-display text-2xl font-bold text-ink">Sections</h2>
                <button
                  onClick={() => setShowSectionMenu(false)}
                  className="text-2xl hover:opacity-70"
                >
                  ✕
                </button>
              </div>
              <nav className="space-y-2">
                {[
                  { key: "overview", label: "Overview", icon: "📊" },
                  { key: "search", label: "Search Cases", icon: "🔍" },
                  { key: "judges", label: "Judges", icon: "⚖️" },
                  { key: "heatmap", label: "Court Heatmap", icon: "🔥" },
                  { key: "analytics", label: "Analytics", icon: "📈" },
                  { key: "delay_detection", label: "Delay Detection", icon: "⚡" },
                  { key: "corrections", label: "Corrections", icon: "✏️" },
                  { key: "feedback", label: "Right-to-Respond", icon: "💬" },
                  { key: "population", label: "Population", icon: "🔄" },
                  { key: "open_data", label: "Open Data", icon: "📂" },
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() => {
                      setSection(item.key as HubSectionKey);
                      setShowSectionMenu(false);
                      setMountedSections(new Set([...mountedSections, item.key as HubSectionKey]));
                    }}
                    className={`w-full text-left px-4 py-2 rounded-lg transition-colors ${
                      section === item.key
                        ? "bg-ocean/10 border border-ocean/60"
                        : "border border-ink/10 hover:bg-white/70"
                    }`}
                  >
                    <p className="text-sm font-semibold text-ink">
                      <span className="mr-2">{item.icon}</span>
                      {item.label}
                    </p>
                  </button>
                ))}
              </nav>
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <section className="grid gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-ink/10 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-ink/60">Total Cases Initiated</p>
          <p className="mt-3 font-display text-4xl font-bold text-ink">{totalCases}</p>
        </div>
        <div className="rounded-xl border border-ink/10 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-ink/60">Pending Cases</p>
          <p className="mt-3 font-display text-4xl font-bold text-ocean">{pendingCases}</p>
        </div>
        <div className="rounded-xl border border-ink/10 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-ink/60">Disposed Cases</p>
          <p className="mt-3 font-display text-4xl font-bold text-ink">{disposedCases}</p>
        </div>
      </section>

      {/* Top Delayed Courts */}
      <section className="space-y-4">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">Top Delayed Courts</h2>
          <p className="mt-1 text-sm text-ink/60">Comparative analysis of judicial bottlenecks across regional jurisdictions based on active case data.</p>
        </div>

        {isLoadingPublic && courtStats.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-14 rounded-lg bg-ink/5 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {courtStats
              .slice()
              .sort((a, b) => b.pending_cases - a.pending_cases)
              .slice(0, 5)
              .map((court) => {
                const maxPending = Math.max(...courtStats.map((c) => c.pending_cases), 1);
                const percentage = (court.pending_cases / maxPending) * 100;
                return (
                  <div key={court.court_id} className="rounded-lg border border-ink/10 bg-white p-4">
                    <div className="flex items-center justify-between gap-4 mb-2">
                      <p className="text-sm font-semibold text-ink flex-1">{court.court_name}</p>
                      <p className="text-right">
                        <span className="text-xs text-ink/60">11 Dec 2024</span>
                      </p>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-ink/10">
                      <div
                        className="h-full bg-gradient-to-r from-ocean to-ocean/70 transition-all"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                    <div className="mt-2 flex justify-between">
                      <p className="text-xs text-ink/60">Pending cases</p>
                      <p className="font-semibold text-ink text-sm">{court.pending_cases}</p>
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </section>

      {/* Recent Flagged Cases */}
      <section className="space-y-4">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">Recent Flagged Cases</h2>
        </div>

        {flags.length === 0 && !isLoadingPublic ? (
          <div className="rounded-lg border border-ink/10 bg-white/50 p-12 text-center">
            <p className="text-sm text-ink/60">No flagged cases at this time</p>
          </div>
        ) : (
          <div className="space-y-2">
            {flags.slice(0, 5).map((flag) => (
              <div key={flag.id} className="rounded-lg border border-ink/10 bg-white p-4 hover:border-ink/20 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="font-semibold text-ink">Case #{flag.case_id}</p>
                    <p className="mt-1 text-sm text-ink/60 capitalize">{flag.flag_type}</p>
                    {flag.details?.summary && (
                      <p className="mt-2 text-sm text-ink/70 line-clamp-2">{flag.details.summary}</p>
                    )}
                  </div>
                  <Link
                    href={`/cases/${flag.case_id}`}
                    className="text-xs font-medium text-ocean hover:underline whitespace-nowrap"
                  >
                    View
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Quick Navigation */}
      <section className="space-y-4">
        <h2 className="font-display text-2xl font-bold text-ink">Quick Access</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Link
            href="/search"
            className="rounded-lg border border-ink/10 bg-white p-5 hover:border-ink/20 hover:bg-white/80 transition-colors group"
          >
            <div className="h-10 w-10 rounded-lg bg-ocean/10 flex items-center justify-center group-hover:bg-ocean/20 transition-colors">
              <span className="text-lg">🔍</span>
            </div>
            <p className="mt-3 font-semibold text-ink">Case Search</p>
            <p className="mt-1 text-xs text-ink/60">Find cases by number</p>
          </Link>

          <Link
            href={"/judges" as Route}
            className="rounded-lg border border-ink/10 bg-white p-5 hover:border-ink/20 hover:bg-white/80 transition-colors group"
          >
            <div className="h-10 w-10 rounded-lg bg-ocean/10 flex items-center justify-center group-hover:bg-ocean/20 transition-colors">
              <span className="text-lg">⚖️</span>
            </div>
            <p className="mt-3 font-semibold text-ink">Judges</p>
            <p className="mt-1 text-xs text-ink/60">Judge performance</p>
          </Link>

          <Link
            href="/analytics"
            className="rounded-lg border border-ink/10 bg-white p-5 hover:border-ink/20 hover:bg-white/80 transition-colors group"
          >
            <div className="h-10 w-10 rounded-lg bg-ocean/10 flex items-center justify-center group-hover:bg-ocean/20 transition-colors">
              <span className="text-lg">📊</span>
            </div>
            <p className="mt-3 font-semibold text-ink">Analytics</p>
            <p className="mt-1 text-xs text-ink/60">Court statistics</p>
          </Link>

          <Link
            href="/delay-detection"
            className="rounded-lg border border-ink/10 bg-white p-5 hover:border-ink/20 hover:bg-white/80 transition-colors group"
          >
            <div className="h-10 w-10 rounded-lg bg-ocean/10 flex items-center justify-center group-hover:bg-ocean/20 transition-colors">
              <span className="text-lg">⚡</span>
            </div>
            <p className="mt-3 font-semibold text-ink">Delay Detection</p>
            <p className="mt-1 text-xs text-ink/60">ML-powered analysis</p>
          </Link>
        </div>
      </section>

      {/* Detailed Section Content */}
      {(section !== "overview" && mountedSections.has(section)) && (
        <section className="border-t border-ink/10 pt-8 mt-8 space-y-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSection("overview")}
              className="text-xs text-ocean hover:underline"
            >
              ← Back to Overview
            </button>
          </div>

          {section === "search" && (
            <div className="card">
              <h3 className="font-display text-xl">Search cases</h3>
              <p className="text-sm text-ink/70">Find cases by case number, court, or party keywords.</p>
              <form onSubmit={submitSearch} className="mt-3 flex gap-2">
                <input
                  className="w-full rounded-lg border border-ink/20 bg-white p-3"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Enter case number, court, or party keyword"
                />
                <button className="rounded-lg bg-ocean px-4 py-2 text-white" type="submit">Search</button>
              </form>
              <div className="card mt-4">
                <h3 className="font-display text-xl">Results</h3>
                {isLoadingSearch ? <SectionSkeleton rows={4} /> : null}
                <ul className="mt-3 space-y-2 text-sm">
                  {searchResults.map((item) => (
                    <li key={item.id} className="rounded-lg border border-ink/10 bg-white p-2">
                      <p className="font-semibold">{item.case_number}</p>
                      <p className="text-ink/70">Status: {item.status}</p>
                      <Link className="text-xs text-ocean underline" href={`/cases/${item.id}`}>Open full case page</Link>
                    </li>
                  ))}
                  {searchResults.length === 0 ? <li>No search results yet.</li> : null}
                </ul>
              </div>
            </div>
          )}

          {section === "judges" && (
            <div className="space-y-4">
              <div className="card">
                <h3 className="font-display text-xl">Judge directory</h3>
                <p className="text-sm text-ink/70">Select a judge to load stats in this panel.</p>
                {isLoadingPublic && judges.length === 0 ? <SectionSkeleton rows={3} /> : null}
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {judges.slice(0, 24).map((judge) => (
                    <button
                      key={judge.id}
                      className={`rounded-lg border px-3 py-2 text-left text-sm ${
                        selectedJudgeId === judge.id ? "border-ocean/60 bg-ocean/10" : "border-ink/10 bg-white"
                      }`}
                      onClick={() => setSelectedJudgeId(judge.id)}
                    >
                      {judge.name}
                    </button>
                  ))}
                </div>
              </div>
              <div className="card">
                <h3 className="font-display text-xl">Judge stats</h3>
                {isLoadingJudgeStats ? <SectionSkeleton rows={2} /> : null}
                {judgeStats ? (
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border border-ink/10 bg-white p-3">
                      <p className="text-xs text-ink/60">Total hearings</p>
                      <p className="text-xl font-semibold">{judgeStats.total_hearings}</p>
                    </div>
                    <div className="rounded-lg border border-ink/10 bg-white p-3">
                      <p className="text-xs text-ink/60">Adjournment rate</p>
                      <p className="text-xl font-semibold">{fmtPercent(judgeStats.adjournment_rate)}</p>
                    </div>
                    <div className="rounded-lg border border-ink/10 bg-white p-3">
                      <p className="text-xs text-ink/60">Median disposal (days)</p>
                      <p className="text-xl font-semibold">{judgeStats.median_disposal_days.toFixed(0)}</p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-ink/70">Pick a judge to view stats.</p>
                )}
              </div>
            </div>
          )}

          {section === "analytics" && (
            <div className="card">
              <h3 className="font-display text-xl">Analytics Dashboard</h3>
              <p className="mt-2 text-sm text-ink/70">Comprehensive insights into case statistics and judicial performance across all courts.</p>
              <Link
                href="/analytics"
                className="mt-4 inline-block rounded bg-ocean px-4 py-2 text-sm text-white hover:bg-ocean/80 transition-colors"
              >
                Open Full Analytics Dashboard →
              </Link>
            </div>
          )}

          {section === "delay_detection" && (
            <div className="card">
              <h3 className="font-display text-xl">Deliberate Delay Detection</h3>
              <p className="text-sm text-ink/70">ML-powered analysis of case adjournment patterns and delays.</p>
              <Link
                href="/delay-detection"
                className="mt-4 inline-block rounded bg-ocean px-4 py-2 text-sm text-white hover:bg-ocean/80 transition-colors"
              >
                Open Delay Detection Tool →
              </Link>
            </div>
          )}

          {section === "heatmap" && (
            <div className="card">
              <h3 className="font-display text-xl">Court delay heatmap</h3>
              {isLoadingPublic && courtStats.length === 0 ? <SectionSkeleton rows={4} /> : null}
              <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {courtStats.map((court) => {
                  const intensity = Math.min(1, court.backlog_ratio);
                  const bg = `rgba(209, 118, 79, ${0.2 + intensity * 0.7})`;
                  return (
                    <div key={court.court_id} className="rounded-lg border border-ink/10 p-3" style={{ background: bg }}>
                      <p className="font-semibold">{court.court_name}</p>
                      <p className="text-sm">Backlog ratio: {fmtPercent(court.backlog_ratio)}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {section === "corrections" && (
            <div className="space-y-4">
              <div className="card">
                <h3 className="font-display text-xl">Submit correction</h3>
                <p className="text-sm text-ink/70">Configure target type and target id, then submit in one step.</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <label className="text-xs text-ink/70">
                    Target type
                    <select
                      className="mt-1 w-full rounded border border-ink/20 p-2"
                      value={correctionTargetType}
                      onChange={(event) => setCorrectionTargetType(event.target.value as "case" | "flag" | "evidence" | "hearing")}
                    >
                      <option value="case">Case</option>
                      <option value="flag">Flag</option>
                      <option value="evidence">Evidence</option>
                      <option value="hearing">Hearing</option>
                    </select>
                  </label>
                  <label className="text-xs text-ink/70">
                    Target id
                    <input
                      className="mt-1 w-full rounded border border-ink/20 p-2"
                      type="number"
                      min={1}
                      value={correctionTargetId}
                      onChange={(event) => setCorrectionTargetId(Number(event.target.value || 1))}
                    />
                  </label>
                </div>
                <div className="mt-3">
                  <CorrectionRequestForm
                    key={`${correctionTargetType}-${correctionTargetId}`}
                    targetType={correctionTargetType}
                    targetId={correctionTargetId}
                  />
                </div>
              </div>
              <div className="card">
                <AdminCorrectionQueue />
              </div>
            </div>
          )}

          {section === "feedback" && (
            <div className="card space-y-3">
              <h3 className="font-display text-xl">Right-to-Respond moderation</h3>
              <label className="block text-sm">
                Admin ID
                <input
                  className="ml-2 w-24 rounded border border-ink/20 p-1"
                  value={feedbackAdminId}
                  onChange={(event) => setFeedbackAdminId(event.target.value)}
                />
              </label>
              <div className="space-y-2">
                {isLoadingFeedback && feedbackRows.length === 0 ? <SectionSkeleton rows={4} /> : null}
                {feedbackRows.map((item) => (
                  <article key={item.id} className="rounded-lg border border-ink/10 bg-white p-3 text-sm">
                    <p className="font-semibold">Case {item.case_id} - {item.responder_name}</p>
                    <p className="text-xs text-ink/70">{item.responder_affiliation || "No affiliation"} - {item.responder_contact}</p>
                    <p className="text-xs text-ink/70">Submitted: {fmtDate(item.submitted_at)}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => feedbackAction(item.id, "verify")}>Verify</button>
                      <button className="rounded bg-emerald-700 px-2 py-1 text-white" onClick={() => feedbackAction(item.id, "publish")}>Publish</button>
                      <button className="rounded bg-amber-700 px-2 py-1 text-white" onClick={() => feedbackAction(item.id, "limit")}>Limit</button>
                      <button className="rounded bg-rose-700 px-2 py-1 text-white" onClick={() => feedbackAction(item.id, "reject")}>Reject</button>
                      <button className="rounded bg-indigo-700 px-2 py-1 text-white" onClick={() => feedbackAction(item.id, "escalate")}>Escalate</button>
                    </div>
                  </article>
                ))}
                {feedbackRows.length === 0 ? <p className="text-sm text-ink/70">No pending feedback items.</p> : null}
              </div>
            </div>
          )}

          {section === "population" && (
            <div className="space-y-4">
              <div className="card">
                <h3 className="font-display text-xl">Population run controls</h3>
                <p className="text-sm text-ink/70">Start and monitor full-source ingestion directly from this panel.</p>
                <div className="mt-3 flex flex-wrap items-end gap-3">
                  <label className="text-xs text-ink/70">
                    Admin ID
                    <input
                      className="mt-1 w-24 rounded border border-ink/20 p-2"
                      value={populationAdminId}
                      onChange={(event) => setPopulationAdminId(event.target.value)}
                    />
                  </label>
                  <label className="min-w-[280px] flex-1 text-xs text-ink/70">
                    Reason
                    <input
                      className="mt-1 w-full rounded border border-ink/20 p-2"
                      value={populationReason}
                      onChange={(event) => setPopulationReason(event.target.value)}
                    />
                  </label>
                  <button
                    className="rounded bg-ocean px-3 py-2 text-xs text-white disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={triggerPopulationRun}
                    disabled={isTriggeringPopulation || hasActivePopulationRun}
                  >
                    {populationButtonText}
                  </button>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <article className="card">
                  <h4 className="font-display text-lg">Recent runs</h4>
                  {isLoadingPopulation && populationRuns.length === 0 ? <SectionSkeleton rows={3} /> : null}
                  <div className="mt-3 space-y-2">
                    {populationRuns.map((run) => (
                      <button
                        key={run.run_id}
                        className="w-full rounded-lg border border-ink/10 bg-white p-2 text-left text-xs hover:bg-slate-50"
                        onClick={() => setSelectedRunId(run.run_id)}
                      >
                        <p className="font-semibold">{run.run_id}</p>
                        <p className="text-ink/70">
                          {run.status} - {run.completed_sources}/{run.total_sources} sources - {run.records_processed} processed
                        </p>
                      </button>
                    ))}
                    {populationRuns.length === 0 ? <p className="text-xs text-ink/70">No runs yet.</p> : null}
                  </div>
                </article>

                <article className="card">
                  <h4 className="font-display text-lg">Run details</h4>
                  {isLoadingPopulationDetail ? <SectionSkeleton rows={2} /> : null}
                  {populationDetail ? (
                    <div className="mt-3 space-y-2 text-xs">
                      <p><span className="font-semibold">Status:</span> {populationDetail.run.status}</p>
                      <p><span className="font-semibold">Trigger:</span> {populationDetail.run.trigger_type}</p>
                      <p><span className="font-semibold">Started:</span> {fmtDate(populationDetail.run.started_at)}</p>
                      <p>
                        <span className="font-semibold">Records:</span> {populationDetail.run.records_processed} processed / {populationDetail.run.records_failed} failed
                      </p>
                      <div className="max-h-72 space-y-1 overflow-auto rounded border border-ink/10 p-2">
                        {populationDetail.sources.map((source) => (
                          <div key={source.id} className="rounded border border-ink/10 p-2">
                            <p className="font-semibold">{source.source_name}</p>
                            <p className="text-ink/70">
                              {source.status} - {source.records_processed} processed - {source.records_failed} failed
                            </p>
                            {source.error_summary ? <p className="text-rose-700">{source.error_summary}</p> : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-ink/70">Select a run to inspect source-level progress.</p>
                  )}
                </article>
              </div>
            </div>
          )}

          {section === "open_data" && (
            <div className="card">
              <h3 className="font-display text-xl">Open data catalog</h3>
              <p className="text-sm text-ink/70">Download datasets directly from this hub.</p>
              {isLoadingPublic && datasets.length === 0 ? <SectionSkeleton rows={3} /> : null}
              <div className="mt-3 space-y-2">
                {datasets.map((dataset) => (
                  <article key={dataset.dataset_id} className="rounded-lg border border-ink/10 bg-white p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold">{dataset.name}</p>
                      <span className="rounded-full bg-ink/5 px-2 py-1 text-xs">v{dataset.version}</span>
                    </div>
                    <p className="mt-1 text-sm text-ink/70">{dataset.description}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <a className="rounded bg-ocean px-2 py-1 text-white" href={`/api/v1/datasets/${dataset.dataset_id}/download?format=csv`}>CSV</a>
                      <a className="rounded bg-accent px-2 py-1 text-white" href={`/api/v1/datasets/${dataset.dataset_id}/download?format=json`}>JSON</a>
                      <a className="rounded border border-ink/20 px-2 py-1" href={`/api/v1/datasets/${dataset.dataset_id}/schema`}>Schema</a>
                    </div>
                  </article>
                ))}
                {datasets.length === 0 ? <p className="text-sm text-ink/70">No datasets available.</p> : null}
              </div>
            </div>
          )}
        </section>
      )}
      <footer className="border-t border-ink/10 pt-8 mt-8">
        <div className="grid gap-8 md:grid-cols-3">
          <div>
            <h4 className="font-semibold text-ink text-sm uppercase tracking-wider">Foundation</h4>
            <p className="mt-3 text-xs text-ink/60 leading-relaxed">
              A comprehensive platform for judicial accountability and case tracking across Indian courts.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-ink text-sm uppercase tracking-wider">Technical</h4>
            <ul className="mt-3 space-y-2 text-xs">
              <li>
                <a
                  href={BACKEND_DOCS_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="text-ink/60 hover:text-ocean transition-colors"
                >
                  API Documentation
                </a>
              </li>
              <li>
                <Link href="/legacy" className="text-ink/60 hover:text-ocean transition-colors">
                  Legacy Interface
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-ink text-sm uppercase tracking-wider">Admin</h4>
            <ul className="mt-3 space-y-2 text-xs">
              <li>
                <Link href="/admin/population" className="text-ink/60 hover:text-ocean transition-colors">
                  Population Controls
                </Link>
              </li>
              <li>
                <Link href="/admin/corrections" className="text-ink/60 hover:text-ocean transition-colors">
                  Moderation Queue
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-8 pt-6 border-t border-ink/10 text-center text-xs text-ink/50">
          <p>© 2026 Judicial Accountability Archive. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}

export default function UnifiedHubPage() {
  return (
    <Suspense fallback={<div className="card text-sm text-ink/70">Loading unified hub...</div>}>
      <UnifiedHubInner />
    </Suspense>
  );
}