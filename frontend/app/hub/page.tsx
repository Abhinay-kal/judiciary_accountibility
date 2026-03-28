"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

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

function SectionSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card animate-pulse space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-10 rounded-lg bg-ink/10" />
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

  const totalCases = useMemo(() => courtStats.reduce((sum, item) => sum + item.total_cases, 0), [courtStats]);
  const pendingCases = useMemo(() => courtStats.reduce((sum, item) => sum + item.pending_cases, 0), [courtStats]);
  const disposedCases = useMemo(() => courtStats.reduce((sum, item) => sum + item.disposed_cases, 0), [courtStats]);

  const updateQueryParams = useCallback(
    (entries: Record<string, string | null>) => {
      const params = new URLSearchParams(window.location.search);
      for (const [key, value] of Object.entries(entries)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }

      const query = params.toString();
      const nextUrl = query ? `${pathname}?${query}` : pathname;
      const currentUrl = `${window.location.pathname}${window.location.search}`;
      if (nextUrl === currentUrl) {
        return;
      }
      window.history.replaceState(null, "", nextUrl);
    },
    [pathname]
  );

  const fetchJsonDedup = useCallback(
    async <T,>(key: string, url: string): Promise<T> => {
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

  async function submitSearch(event: FormEvent) {
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
    <div className="space-y-4">
      <header className="card flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="font-display text-3xl text-ink">Unified Operations Hub</h1>
          <p className="text-sm text-ink/70">
            One place for public insights and admin actions. Use the left menu to switch sections without changing pages.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/legacy" className="rounded-lg border border-ink/20 px-3 py-2 hover:bg-white/70">Legacy Home</Link>
          <a href={BACKEND_DOCS_URL} className="rounded-lg border border-ink/20 px-3 py-2 hover:bg-white/70" target="_blank" rel="noreferrer">API Docs</a>
          <Link href="/admin/population" className="rounded-lg border border-ink/20 px-3 py-2 hover:bg-white/70">Population Page</Link>
        </div>
      </header>

      {message ? <p className="rounded-lg border border-ink/20 bg-white/70 px-3 py-2 text-sm text-ink/80">{message}</p> : null}

      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="card h-fit lg:sticky lg:top-6">
          <h2 className="font-display text-xl">Sections</h2>
          <p className="mt-1 text-xs text-ink/65">Everything is available in this single interface.</p>
          <nav className="mt-3 space-y-2">
            {SECTIONS.map((item) => (
              <button
                key={item.key}
                className={`w-full rounded-lg border px-3 py-2 text-left ${
                  section === item.key
                    ? "border-ocean/60 bg-ocean/10"
                    : "border-ink/10 bg-white/70 hover:bg-white"
                }`}
                onClick={() => setSection(item.key)}
              >
                <p className="text-sm font-semibold text-ink">{item.label}</p>
                <p className="text-xs text-ink/70">{item.helper}</p>
              </button>
            ))}
          </nav>

          <div className="mt-4 space-y-2 rounded-xl border border-ink/10 bg-white/80 p-3 text-xs">
            <p><span className="font-semibold">Total Cases:</span> {totalCases}</p>
            <p><span className="font-semibold">Flags:</span> {flags.length}</p>
            <p><span className="font-semibold">Pending Feedback:</span> {feedbackRows.length}</p>
            <p><span className="font-semibold">Active Runs:</span> {populationRuns.filter((run) => ACTIVE_STATUSES.has(run.status)).length}</p>
          </div>
        </aside>

        <section className="space-y-4">
          {section === "overview" || mountedSections.has("overview") ? (
            <div className={section === "overview" ? "space-y-4" : "hidden"}>
              {isLoadingPublic && courtStats.length === 0 ? <SectionSkeleton rows={5} /> : null}
              <div className="grid gap-3 md:grid-cols-3">
                <div className="card"><p className="text-xs text-ink/60">Total Cases</p><p className="font-display text-3xl">{totalCases}</p></div>
                <div className="card"><p className="text-xs text-ink/60">Pending Cases</p><p className="font-display text-3xl">{pendingCases}</p></div>
                <div className="card"><p className="text-xs text-ink/60">Disposed Cases</p><p className="font-display text-3xl">{disposedCases}</p></div>
              </div>

              <DelayBarChart
                data={courtStats
                  .slice()
                  .sort((a, b) => b.pending_cases - a.pending_cases)
                  .slice(0, 8)
                  .map((item) => ({ court: item.court_name, pending: item.pending_cases }))}
              />

              <div className="card">
                <h3 className="font-display text-xl">Recent flagged cases</h3>
                <ul className="mt-3 space-y-2 text-sm">
                  {flags.map((item) => (
                    <li key={item.id} className="rounded-lg border border-ink/10 bg-white p-2">
                      <p className="font-semibold">Case #{item.case_id} - {item.flag_type}</p>
                      {item.details?.summary ? <p className="mt-1 text-xs text-ink/70">{item.details.summary}</p> : null}
                    </li>
                  ))}
                  {flags.length === 0 ? <li>No flagged cases yet.</li> : null}
                </ul>
              </div>
            </div>
          ) : null}

          {section === "search" || mountedSections.has("search") ? (
            <div className={section === "search" ? "space-y-4" : "hidden"}>
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
              </div>

              <div className="card">
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
          ) : null}

          {section === "judges" || mountedSections.has("judges") ? (
            <div className={section === "judges" ? "space-y-4" : "hidden"}>
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
          ) : null}

          {section === "analytics" ? (
            <div className="card">
              <h3 className="font-display text-xl">Analytics Dashboard</h3>
              <p className="mt-2 text-sm text-ink/70">Comprehensive insights into case statistics and judicial performance across all courts.</p>
              <p className="mt-3 text-sm">
                Access detailed analytics including:
              </p>
              <ul className="mt-2 space-y-1 text-sm text-ink/70">
                <li>• Case summary statistics (total, pending, disposed)</li>
                <li>• Court performance metrics and comparative analysis</li>
                <li>• Case distribution across courts and by type</li>
                <li>• Disposal status trends and patterns</li>
                <li>• 12-month filing trends and forecasts</li>
              </ul>
              <Link
                href="/analytics"
                className="mt-4 inline-block rounded bg-ocean px-4 py-2 text-sm text-white hover:bg-ocean/80 transition-colors"
              >
                Open Analytics Dashboard →
              </Link>
            </div>
          ) : null}

          {section === "heatmap" || mountedSections.has("heatmap") ? (
            <div className={section === "heatmap" ? "card" : "hidden"}>
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
          ) : null}

          {section === "open_data" || mountedSections.has("open_data") ? (
            <div className={section === "open_data" ? "card" : "hidden"}>
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
          ) : null}

          {section === "delay_detection" || mountedSections.has("delay_detection") ? (
            <div className={section === "delay_detection" ? "space-y-4" : "hidden"}>
              <div className="card">
                <h3 className="font-display text-xl">Deliberate Delay Detection</h3>
                <p className="text-sm text-ink/70">ML-powered analysis of case adjournment patterns and delays. Analyze single cases or batch process up to 1,000 cases.</p>
              </div>

              {/* Tabs for delay detection sections */}
              <div className="flex gap-2 overflow-x-auto">
                <button
                  onClick={() => {
                    // This is handled in the components
                  }}
                  className="px-4 py-2 rounded-lg bg-ocean text-white font-medium whitespace-nowrap"
                >
                  Single Case
                </button>
                <button className="px-4 py-2 rounded-lg bg-ink/10 text-ink/70 font-medium whitespace-nowrap">
                  Batch Analysis
                </button>
                <button className="px-4 py-2 rounded-lg bg-ink/10 text-ink/70 font-medium whitespace-nowrap">
                  Baseline Metrics
                </button>
              </div>

              {/* Single Case Search */}
              <CaseDelaySearch />

              {/* Baseline Metrics */}
              <BaselineMetrics />

              {/* Batch Analysis */}
              <BatchDelayAnalysis />
            </div>
          ) : null}

          {section === "corrections" || mountedSections.has("corrections") ? (
            <div className={section === "corrections" ? "space-y-4" : "hidden"}>
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
          ) : null}

          {section === "feedback" || mountedSections.has("feedback") ? (
            <div className={section === "feedback" ? "card space-y-3" : "hidden"}>
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
          ) : null}

          {section === "population" || mountedSections.has("population") ? (
            <div className={section === "population" ? "space-y-4" : "hidden"}>
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
                    {hasActivePopulationRun ? "Run in progress" : isTriggeringPopulation ? "Queueing..." : "Start population"}
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
          ) : null}
        </section>
      </div>
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