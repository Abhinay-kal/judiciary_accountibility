export default function GlobalLoading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      <div className="card animate-pulse space-y-3">
        <div className="h-7 w-56 rounded bg-ink/10" />
        <div className="h-4 w-72 rounded bg-ink/10" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="card animate-pulse"><div className="h-20 rounded bg-ink/10" /></div>
        <div className="card animate-pulse"><div className="h-20 rounded bg-ink/10" /></div>
        <div className="card animate-pulse"><div className="h-20 rounded bg-ink/10" /></div>
      </div>
      <div className="card animate-pulse"><div className="h-48 rounded bg-ink/10" /></div>
    </div>
  );
}