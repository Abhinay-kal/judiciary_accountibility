"use client";

import { FormEvent, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export function SubmitOfficialResponseForm({ caseId }: { caseId: number }) {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const formData = new FormData(event.currentTarget);

    const response = await fetch(`${API_BASE}/feedback/case/${caseId}`, {
      method: "POST",
      body: formData,
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      setMessage(payload.detail || "Submission failed");
      setLoading(false);
      return;
    }

    setMessage(`Submitted feedback ${payload.feedback_id}. ${payload.verification_instructions}`);
    setLoading(false);
    (event.currentTarget as HTMLFormElement).reset();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2 rounded-lg border border-ink/10 bg-white p-4">
      <h3 className="font-display text-lg">Submit official response</h3>
      <p className="text-xs text-ink/70">Authorized responders can submit a right-to-respond statement and complete verification.</p>
      <input className="w-full rounded border border-ink/20 p-2" name="responder_name" placeholder="Responder name" required />
      <input className="w-full rounded border border-ink/20 p-2" name="responder_affiliation" placeholder="Affiliation" required />
      <input className="w-full rounded border border-ink/20 p-2" name="responder_contact" type="email" placeholder="Official email" required />
      <select className="w-full rounded border border-ink/20 p-2" name="responder_type" defaultValue="GOV_AGENCY">
        <option value="INDIVIDUAL">Individual</option>
        <option value="GOV_AGENCY">Government agency</option>
        <option value="COMPANY">Company</option>
        <option value="LAW_FIRM">Law firm</option>
        <option value="NGO">NGO</option>
      </select>
      <textarea className="w-full rounded border border-ink/20 p-2" name="content" rows={4} placeholder="Official response content" required />
      <select className="w-full rounded border border-ink/20 p-2" name="preferred_display_label" defaultValue="OFFICIAL_RESPONSE">
        <option value="OFFICIAL_RESPONSE">Official response</option>
        <option value="RESPONSE_FROM_PARTY">Response from party</option>
        <option value="CLARIFICATION">Clarification</option>
      </select>
      <input className="w-full text-xs" name="attachments" type="file" multiple />
      <input className="w-full text-xs" name="letter_of_authority_upload" type="file" />
      <button disabled={loading} className="rounded bg-ocean px-4 py-2 text-white" type="submit">{loading ? "Submitting..." : "Submit official response"}</button>
      {message ? <p className="text-xs text-ink/70">{message}</p> : null}
    </form>
  );
}
