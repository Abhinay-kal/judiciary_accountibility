type EvidenceBadgeProps = {
  label: "Data anomaly" | "Unusual delay pattern" | "Requires verification" | "Verified";
  confidence?: number;
  explanation?: string;
  provenanceLinks?: string[];
};

const badgeColor: Record<EvidenceBadgeProps["label"], string> = {
  "Data anomaly": "bg-amber-100 text-amber-900",
  "Unusual delay pattern": "bg-orange-100 text-orange-900",
  "Requires verification": "bg-slate-200 text-slate-900",
  Verified: "bg-emerald-100 text-emerald-900",
};

export function EvidenceBadge({ label, confidence, explanation, provenanceLinks }: EvidenceBadgeProps) {
  const pct = typeof confidence === "number" ? Math.round(Math.max(0, Math.min(1, confidence)) * 100) : null;

  return (
    <div className="space-y-2 rounded-lg border border-ink/10 bg-white p-3">
      <div className="flex items-center gap-2">
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeColor[label]}`}>{label}</span>
        {pct !== null ? <span className="text-xs text-ink/70">Confidence: {pct}%</span> : null}
      </div>

      {pct !== null ? (
        <div className="h-2 w-full rounded bg-ink/10" aria-label="confidence meter">
          <div className="h-2 rounded bg-ocean" style={{ width: `${pct}%` }} />
        </div>
      ) : null}

      <details className="text-xs text-ink/80">
        <summary className="cursor-pointer font-semibold">Why this label?</summary>
        <p className="mt-2">{explanation || "Automated moderation context unavailable."}</p>
        {provenanceLinks?.length ? (
          <ul className="mt-2 list-disc pl-5">
            {provenanceLinks.map((link) => (
              <li key={link}>
                <a className="underline" href={link} target="_blank" rel="noreferrer">
                  {link}
                </a>
              </li>
            ))}
          </ul>
        ) : null}
      </details>
    </div>
  );
}
