"use client";

import { FormEvent, useState } from "react";

type Props = {
  targetType: "case" | "flag" | "evidence" | "hearing";
  targetId: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function CorrectionRequestForm({ targetType, targetId }: Props) {
  const [message, setMessage] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");

    const formData = new FormData(event.currentTarget);
    formData.set("target_type", targetType);
    formData.set("target_id", String(targetId));

    const response = await fetch(`${API_BASE}/corrections/requests`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setMessage(payload.detail || "Failed to submit correction request");
      setLoading(false);
      return;
    }

    const payload = await response.json();
    setMessage(`Submitted request #${payload.id}. Status: ${payload.status}.`);
    setLoading(false);
    (event.currentTarget as HTMLFormElement).reset();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-lg border border-ink/10 bg-white p-4">
      <h3 className="font-display text-lg">Request a correction / right-to-respond</h3>
      <input className="w-full rounded border border-ink/20 p-2" name="requester_name" placeholder="Your name" required />
      <input className="w-full rounded border border-ink/20 p-2" name="requester_contact" placeholder="Email or phone" required />
      <input className="w-full rounded border border-ink/20 p-2" name="requester_affiliation" placeholder="Affiliation (optional)" />
      <textarea className="w-full rounded border border-ink/20 p-2" name="request_reason" rows={4} placeholder="Describe the correction needed" required />
      <input className="w-full text-sm" type="file" name="evidence_file" accept=".pdf,.png,.jpg,.jpeg" />
      <button disabled={loading} className="rounded bg-ocean px-4 py-2 text-white" type="submit">
        {loading ? "Submitting..." : "Submit correction request"}
      </button>
      {message ? <p className="text-sm text-ink/80">{message}</p> : null}
    </form>
  );
}
