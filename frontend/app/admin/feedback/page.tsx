"use client";

import { useEffect, useState } from "react";

type PendingItem = {
  id: string;
  case_id: number;
  responder_name: string;
  responder_affiliation?: string;
  responder_contact: string;
  responder_verified: boolean;
  submitted_at: string;
  moderation_notes?: Record<string, unknown>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export default function AdminFeedbackPage() {
  const [rows, setRows] = useState<PendingItem[]>([]);
  const [adminId, setAdminId] = useState("1");
  const [message, setMessage] = useState("");

  async function load() {
    const response = await fetch(`${API_BASE}/admin/feedback/pending`);
    const payload = await response.json();
    setRows(payload.items || []);
  }

  useEffect(() => {
    load();
  }, []);

  async function act(id: string, action: "verify" | "publish" | "reject" | "limit" | "escalate") {
    const body: Record<string, unknown> = { admin_id: Number(adminId) };
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
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMessage(payload.detail || `Action ${action} failed`);
      return;
    }
    setMessage(`Action ${action} completed for ${id}`);
    load();
  }

  return (
    <main className="space-y-4">
      <h1 className="font-display text-3xl">Admin feedback moderation</h1>
      <p className="text-sm text-ink/70">Review, verify, publish, redact, reject, or escalate RtR responses.</p>
      <label className="block text-sm">
        Admin ID
        <input className="ml-2 w-24 rounded border border-ink/20 p-1" value={adminId} onChange={(event) => setAdminId(event.target.value)} />
      </label>
      {message ? <p className="text-xs text-ink/70">{message}</p> : null}

      <section className="space-y-3">
        {rows.map((item) => (
          <article key={item.id} className="rounded-md border border-ink/10 bg-white p-3 text-sm">
            <p className="font-semibold">Case {item.case_id} · {item.responder_name}</p>
            <p className="text-xs text-ink/70">{item.responder_affiliation || "No affiliation"} · {item.responder_contact}</p>
            <p className="text-xs text-ink/70">Submitted: {new Date(item.submitted_at).toLocaleString()}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <button className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => act(item.id, "verify")}>Verify</button>
              <button className="rounded bg-emerald-700 px-2 py-1 text-white" onClick={() => act(item.id, "publish")}>Publish</button>
              <button className="rounded bg-amber-700 px-2 py-1 text-white" onClick={() => act(item.id, "limit")}>Limit</button>
              <button className="rounded bg-rose-700 px-2 py-1 text-white" onClick={() => act(item.id, "reject")}>Reject</button>
              <button className="rounded bg-indigo-700 px-2 py-1 text-white" onClick={() => act(item.id, "escalate")}>Escalate</button>
            </div>
            <a className="mt-2 inline-block text-xs underline" href={`${API_BASE}/admin/feedback/${item.id}/audit`} target="_blank" rel="noreferrer">View audit log</a>
          </article>
        ))}
      </section>
    </main>
  );
}
