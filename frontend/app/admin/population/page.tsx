"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type PopulationRunItem = {
  run_id: string;
  trigger_type: string;
  status: string;
  admin_id: number | null;
  started_at: string;
  finished_at: string | null;
  total_sources: number;
  completed_sources: number;
  successful_sources: number;
  failed_sources: number;
  records_processed: number;
  records_failed: number;
  reason?: string | null;
};

type PopulationSourceItem = {
  id: number;
  source_id: number;
  source_name: string;
  status: string;
  task_id?: string | null;
  records_processed: number;
  records_failed: number;
  error_summary?: string | null;
  started_at: string;
  finished_at?: string | null;
};

type PopulationRunDetail = {
  run: PopulationRunItem & { diagnostics?: Record<string, unknown> };
  sources: PopulationSourceItem[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";
const ACTIVE_STATUSES = new Set(["QUEUED", "RUNNING"]);

export default function AdminPopulationPage() {
  const [adminId, setAdminId] = useState("1");
  const [reason, setReason] = useState("Manual admin population run");
  const [message, setMessage] = useState("");
  const [runs, setRuns] = useState<PopulationRunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PopulationRunDetail | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);

  const hasActiveRun = useMemo(() => runs.some((run) => ACTIVE_STATUSES.has(run.status)), [runs]);
  let triggerButtonLabel = "Start population";
  if (hasActiveRun) {
    triggerButtonLabel = "Run in progress";
  } else if (isTriggering) {
    triggerButtonLabel = "Queueing...";
  }

  const loadRuns = useCallback(async () => {
    const response = await fetch(`${API_BASE}/admin/population/runs?limit=25&offset=0`);
    const payload = await response.json().catch(() => ({ items: [] }));
    setRuns(payload.items || []);

    if (!selectedRunId && payload.items?.length) {
      setSelectedRunId(payload.items[0].run_id);
    }
  }, [selectedRunId]);

  const loadRunDetail = useCallback(async (runId: string) => {
    const response = await fetch(`${API_BASE}/admin/population/runs/${runId}`);
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload) {
      setMessage(payload?.detail || `Failed to load run ${runId}`);
      return;
    }
    setDetail(payload);
  }, []);

  async function triggerPopulationRun() {
    setIsTriggering(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/admin/population/runs/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_id: Number(adminId), reason }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setMessage(payload.detail || "Failed to trigger population run");
        return;
      }
      setMessage(payload.status === "already_running" ? `Run already active: ${payload.run_id}` : `Run queued: ${payload.run_id}`);
      await loadRuns();
      if (payload.run_id) {
        setSelectedRunId(payload.run_id);
        await loadRunDetail(payload.run_id);
      }
    } finally {
      setIsTriggering(false);
    }
  }

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    loadRunDetail(selectedRunId);
  }, [selectedRunId, loadRunDetail]);

  useEffect(() => {
    const interval = setInterval(() => {
      loadRuns();
      if (selectedRunId) {
        loadRunDetail(selectedRunId);
      }
    }, hasActiveRun ? 5000 : 15000);
    return () => clearInterval(interval);
  }, [hasActiveRun, selectedRunId, loadRuns, loadRunDetail]);

  return (
    <main className="space-y-4">
      <h1 className="font-display text-3xl">Admin population runs</h1>
      <p className="text-sm text-ink/70">Start full-source data population and monitor source-level progress.</p>

      <section className="rounded-lg border border-ink/10 bg-white p-3 text-sm">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="text-xs text-ink/70">Admin ID</span>
            <input
              className="mt-1 w-24 rounded border border-ink/20 p-1"
              value={adminId}
              onChange={(event) => setAdminId(event.target.value)}
            />
          </label>
          <label className="block min-w-[260px] flex-1">
            <span className="text-xs text-ink/70">Reason</span>
            <input
              className="mt-1 w-full rounded border border-ink/20 p-1"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button
            className="rounded bg-ocean px-3 py-2 text-xs text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={triggerPopulationRun}
            disabled={isTriggering || hasActiveRun}
          >
            {triggerButtonLabel}
          </button>
        </div>
        {message ? <p className="mt-2 text-xs text-ink/70">{message}</p> : null}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-lg border border-ink/10 bg-white p-3">
          <h2 className="text-sm font-semibold">Recent runs</h2>
          <div className="mt-2 space-y-2">
            {runs.map((run) => (
              <button
                key={run.run_id}
                className="w-full rounded border border-ink/10 p-2 text-left text-xs hover:bg-slate-50"
                onClick={() => setSelectedRunId(run.run_id)}
              >
                <p className="font-semibold">{run.run_id}</p>
                <p className="text-ink/70">{run.status} · {run.completed_sources}/{run.total_sources} sources · {run.records_processed} processed</p>
              </button>
            ))}
            {runs.length === 0 ? <p className="text-xs text-ink/70">No runs found.</p> : null}
          </div>
        </article>

        <article className="rounded-lg border border-ink/10 bg-white p-3">
          <h2 className="text-sm font-semibold">Run details</h2>
          {detail ? (
            <div className="mt-2 space-y-2 text-xs">
              <p><span className="font-semibold">Status:</span> {detail.run.status}</p>
              <p><span className="font-semibold">Trigger:</span> {detail.run.trigger_type}</p>
              <p><span className="font-semibold">Sources:</span> {detail.run.completed_sources}/{detail.run.total_sources}</p>
              <p><span className="font-semibold">Records:</span> {detail.run.records_processed} processed / {detail.run.records_failed} failed</p>
              <div className="max-h-72 space-y-1 overflow-auto rounded border border-ink/10 p-2">
                {detail.sources.map((source) => (
                  <div key={source.id} className="rounded border border-ink/10 p-2">
                    <p className="font-semibold">{source.source_name}</p>
                    <p className="text-ink/70">{source.status} · {source.records_processed} processed · {source.records_failed} failed</p>
                    {source.error_summary ? <p className="text-rose-700">{source.error_summary}</p> : null}
                  </div>
                ))}
                {detail.sources.length === 0 ? <p className="text-ink/70">No source runs recorded.</p> : null}
              </div>
            </div>
          ) : <p className="mt-2 text-xs text-ink/70">Select a run to inspect progress.</p>}
        </article>
      </section>
    </main>
  );
}
