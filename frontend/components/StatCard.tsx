type Props = {
  label: string;
  value: string | number;
  delta?: string;
};

export function StatCard({ label, value, delta }: Props) {
  return (
    <article className="card">
      <p className="text-sm uppercase tracking-wider text-ink/60">{label}</p>
      <p className="mt-2 font-display text-3xl text-ocean">{value}</p>
      {delta ? <p className="mt-2 text-xs text-clay">{delta}</p> : null}
    </article>
  );
}
