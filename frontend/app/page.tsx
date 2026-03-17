import { DelayBarChart } from "@/components/DelayBarChart";
import { StatCard } from "@/components/StatCard";
import { getJSON } from "@/components/api";
import Link from "next/link";

type CourtStat = {
  court_id: number;
  court_name: string;
  total_cases: number;
  pending_cases: number;
  disposed_cases: number;
  backlog_ratio: number;
};

type FlagsResponse = {
  items: Array<{ id: number; case_id: number; flag_type: string }>;
};

export default async function HomePage() {
  const [courtStats, flags] = await Promise.all([
    getJSON<CourtStat[]>("/stats/court").catch(() => []),
    getJSON<FlagsResponse>("/flags").catch(() => ({ items: [] }))
  ]);

  const totalCases = courtStats.reduce((sum, c) => sum + c.total_cases, 0);
  const pendingCases = courtStats.reduce((sum, c) => sum + c.pending_cases, 0);
  const disposedCases = courtStats.reduce((sum, c) => sum + c.disposed_cases, 0);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Court Case Delay & Justice Tracker - India</h1>
        <p className="max-w-3xl text-sm text-ink/70">
          Data aggregated from public judicial sources. Verify with official records.
        </p>
        <Link href="/open-data" className="inline-block rounded-lg bg-ocean px-4 py-2 text-sm font-semibold text-white">
          Explore Open Data Catalog
        </Link>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <StatCard label="Total Cases" value={totalCases} />
        <StatCard label="Pending Cases" value={pendingCases} />
        <StatCard label="Disposed Cases" value={disposedCases} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <DelayBarChart
          data={courtStats
            .sort((a, b) => b.pending_cases - a.pending_cases)
            .slice(0, 8)
            .map((c) => ({ court: c.court_name, pending: c.pending_cases }))}
        />

        <div className="card">
          <h3 className="font-display text-lg">Recent Flagged Cases</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {flags.items.slice(0, 8).map((f) => (
              <li key={f.id} className="rounded-lg bg-white p-2">
                Case #{f.case_id} - {f.flag_type}
              </li>
            ))}
            {flags.items.length === 0 ? <li>No flagged cases yet.</li> : null}
          </ul>
        </div>
      </section>
    </div>
  );
}
