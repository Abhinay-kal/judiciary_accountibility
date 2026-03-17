type Hearing = {
  id: number;
  date: string;
  outcome_text?: string;
  source: string;
};

export function Timeline({ hearings }: { hearings: Hearing[] }) {
  return (
    <ol className="space-y-3">
      {hearings.map((h) => (
        <li key={h.id} className="card border-l-4 border-ocean">
          <p className="font-semibold">{h.date}</p>
          <p className="text-sm text-ink/80">{h.outcome_text ?? "No outcome text"}</p>
          <a href={h.source} className="text-xs text-clay underline">
            Source
          </a>
        </li>
      ))}
    </ol>
  );
}
