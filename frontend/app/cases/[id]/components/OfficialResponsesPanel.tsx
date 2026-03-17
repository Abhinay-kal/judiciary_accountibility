"use client";

import { useEffect, useMemo, useState } from "react";

type FeedbackItem = {
  id: string;
  responder_name: string;
  responder_affiliation?: string;
  responder_verified: boolean;
  responder_verification_method?: string | null;
  submitted_at: string;
  display_label: string;
  public_status: "PENDING_REVIEW" | "PUBLISHED" | "REJECTED" | "LIMITED";
  public_note?: string | null;
  content?: string | null;
  attachments?: Array<{ filename: string; storage_ref: string }>;
  placeholder?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function OfficialResponsesPanel({ caseId }: { caseId: number }) {
  const [rows, setRows] = useState<FeedbackItem[]>([]);
  const [tab, setTab] = useState<"published" | "pending" | "all">("published");

  useEffect(() => {
    fetch(`${API_BASE}/feedback/case/${caseId}`)
      .then((response) => response.json())
      .then((payload) => setRows(payload.items || []))
      .catch(() => setRows([]));
  }, [caseId]);

  const visible = useMemo(() => {
    if (tab === "all") {
      return rows;
    }
    if (tab === "pending") {
      return rows.filter((item) => item.public_status === "PENDING_REVIEW");
    }
    return rows.filter((item) => item.public_status === "PUBLISHED" || item.public_status === "LIMITED");
  }, [rows, tab]);

  return (
    <section className="space-y-3 rounded-lg border border-ink/10 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl">Official responses</h2>
        <div className="flex gap-2 text-xs">
          <button className="rounded border border-ink/20 px-2 py-1" onClick={() => setTab("published")}>Published</button>
          <button className="rounded border border-ink/20 px-2 py-1" onClick={() => setTab("pending")}>Pending</button>
          <button className="rounded border border-ink/20 px-2 py-1" onClick={() => setTab("all")}>All</button>
        </div>
      </div>

      {visible.map((item) => (
        <article key={item.id} className="rounded-md border border-ink/10 p-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <p className="font-semibold">{item.display_label.replaceAll("_", " ")}</p>
            <span className="text-xs text-ink/70">{new Date(item.submitted_at).toLocaleString()}</span>
          </div>
          <p className="mt-1 text-xs text-ink/70">
            {item.responder_affiliation || item.responder_name} · {item.responder_verified ? "Verified" : "Not verified"}
          </p>
          {item.responder_verified ? (
            <p className="text-xs text-ink/70">This response was submitted by {item.responder_name}, verified via {item.responder_verification_method || "admin review"}.</p>
          ) : (
            <p className="text-xs text-ink/70">Submitted and pending verification.</p>
          )}
          {item.public_note ? <p className="mt-2">{item.public_note}</p> : null}
          {item.content ? <p className="mt-2 whitespace-pre-wrap">{item.content}</p> : null}
          {item.placeholder ? <p className="mt-2 text-ink/80">{item.placeholder}</p> : null}
          {item.attachments?.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs">
              {item.attachments.map((attachment) => (
                <li key={attachment.storage_ref}>{attachment.filename}</li>
              ))}
            </ul>
          ) : null}
          <a className="mt-2 inline-block text-xs underline" href="/corrections">Report issue with this response</a>
        </article>
      ))}

      {!visible.length ? <p className="text-sm text-ink/60">No responses available for this tab.</p> : null}
    </section>
  );
}
