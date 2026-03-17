"use client";

import { FormEvent, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function ModerationRedactionTool() {
  const [output, setOutput] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      admin_id: Number(form.get("admin_id") || 0),
      target_type: String(form.get("target_type") || "case"),
      target_id: Number(form.get("target_id") || 0),
      reason: String(form.get("reason") || "Legal-safe redaction"),
      text: String(form.get("text") || ""),
    };
    const response = await fetch(`${API_BASE}/corrections/admin/redact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    setOutput(response.ok ? data.public_note || "Redacted" : data.detail || "Failed");
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2 rounded-lg border border-ink/10 bg-white p-3">
      <h3 className="font-display text-lg">Redaction tool</h3>
      <input className="w-full rounded border border-ink/20 p-2" name="admin_id" placeholder="admin_id" required />
      <div className="grid grid-cols-2 gap-2">
        <input className="rounded border border-ink/20 p-2" name="target_type" defaultValue="case" required />
        <input className="rounded border border-ink/20 p-2" name="target_id" placeholder="target_id" required />
      </div>
      <input className="w-full rounded border border-ink/20 p-2" name="reason" placeholder="Reason" required />
      <textarea className="w-full rounded border border-ink/20 p-2" name="text" rows={3} placeholder="Raw public text to sanitize" required />
      <button className="rounded bg-amber-700 px-3 py-2 text-xs text-white" type="submit">Apply redaction</button>
      {output ? <p className="text-xs text-ink/70">{output}</p> : null}
    </form>
  );
}
