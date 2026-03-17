"use client";

import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";

type CorrectionItem = {
  id: number;
  target_type: string;
  target_id: number;
  requester_name: string;
  requester_contact: string;
  request_reason: string;
  status: string;
  assigned_admin?: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function AdminCorrectionQueue() {
  const [rows, setRows] = useState<CorrectionItem[]>([]);
  const [adminId, setAdminId] = useState("1");

  async function load() {
    const response = await fetch(`${API_BASE}/admin/corrections/pending`);
    const payload = await response.json();
    setRows(payload.items || []);
  }

  useEffect(() => {
    load();
  }, []);

  async function review(id: number, status: "ACCEPTED" | "REJECTED" | "ESCALATED") {
    await fetch(`${API_BASE}/admin/corrections/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_id: Number(adminId),
        status,
        reason: "Admin moderation decision",
        notes: { source: "admin_queue" },
      }),
    });
    load();
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="font-display text-2xl">Pending corrections</h2>
        <input
          className="w-24 rounded border border-ink/20 p-1 text-sm"
          value={adminId}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setAdminId(event.target.value)}
          placeholder="admin"
        />
      </div>

      <ul className="space-y-2">
        {rows.map((item) => (
          <li key={item.id} className="rounded-lg border border-ink/10 bg-white p-3">
            <p className="font-semibold">#{item.id} · {item.target_type}:{item.target_id}</p>
            <p className="text-sm text-ink/70">{item.requester_name} ({item.requester_contact})</p>
            <p className="mt-1 text-sm">{item.request_reason}</p>
            <p className="mt-1 text-xs text-ink/60">Status: {item.status}</p>
            <div className="mt-2 flex gap-2">
              <button className="rounded bg-emerald-600 px-3 py-1 text-xs text-white" onClick={() => review(item.id, "ACCEPTED")}>Accept</button>
              <button className="rounded bg-rose-600 px-3 py-1 text-xs text-white" onClick={() => review(item.id, "REJECTED")}>Reject</button>
              <button className="rounded bg-amber-600 px-3 py-1 text-xs text-white" onClick={() => review(item.id, "ESCALATED")}>Escalate</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
