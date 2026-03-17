"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

type AuditRow = {
  id: number;
  action_type: string;
  target_type: string;
  target_id: number;
  admin_id?: number;
  reason: string;
  created_at: string;
};

export function ModerationAuditTrailViewer() {
  const [rows, setRows] = useState<AuditRow[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/corrections/admin/moderation-logs`)
      .then((response) => response.json())
      .then((payload) => setRows(payload.items || []))
      .catch(() => setRows([]));
  }, []);

  return (
    <section className="space-y-2 rounded-lg border border-ink/10 bg-white p-3">
      <h3 className="font-display text-lg">Audit trail</h3>
      <ul className="space-y-2">
        {rows.slice(0, 20).map((row) => (
          <li key={row.id} className="rounded border border-ink/10 p-2 text-xs">
            <p className="font-semibold">{row.action_type} · {row.target_type}:{row.target_id}</p>
            <p>{row.reason}</p>
            <p className="text-ink/60">admin={row.admin_id || "system"} · {row.created_at}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
