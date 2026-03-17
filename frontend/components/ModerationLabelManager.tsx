"use client";

import { FormEvent, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function ModerationLabelManager() {
  const [message, setMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      admin_id: Number(form.get("admin_id") || 0),
      target_type: String(form.get("target_type") || "case"),
      target_id: Number(form.get("target_id") || 0),
      label: String(form.get("label") || "UNVERIFIED"),
      label_confidence: Number(form.get("label_confidence") || 0.6),
      explanation: String(form.get("explanation") || "Admin label decision"),
    };
    const response = await fetch(`${API_BASE}/corrections/admin/labels/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMessage(data.detail || "Failed to add label");
      return;
    }
    setMessage(`Label created: #${data.label_id}`);
    (event.currentTarget as HTMLFormElement).reset();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2 rounded-lg border border-ink/10 bg-white p-3">
      <h3 className="font-display text-lg">Label management</h3>
      <div className="grid grid-cols-2 gap-2">
        <input className="rounded border border-ink/20 p-2" name="admin_id" placeholder="admin_id" required />
        <input className="rounded border border-ink/20 p-2" name="target_id" placeholder="target_id" required />
        <input className="rounded border border-ink/20 p-2" name="target_type" placeholder="case/flag/evidence/hearing" defaultValue="case" required />
        <input className="rounded border border-ink/20 p-2" name="label" placeholder="UNVERIFIED" defaultValue="UNVERIFIED" required />
        <input className="rounded border border-ink/20 p-2" name="label_confidence" placeholder="0.6" defaultValue="0.6" required />
        <input className="rounded border border-ink/20 p-2" name="explanation" placeholder="Required moderation explanation" required />
      </div>
      <button className="rounded bg-ocean px-3 py-2 text-xs text-white" type="submit">Add label</button>
      {message ? <p className="text-xs text-ink/70">{message}</p> : null}
    </form>
  );
}
