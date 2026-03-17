import { getJSON } from "@/components/api";

type CourtStat = {
  court_id: number;
  court_name: string;
  backlog_ratio: number;
};

export default async function HeatmapPage() {
  const stats = await getJSON<CourtStat[]>("/stats/court").catch(() => []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Court Delay Heatmap</h1>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {stats.map((court) => {
          const intensity = Math.min(1, court.backlog_ratio);
          const bg = `rgba(209, 118, 79, ${0.2 + intensity * 0.7})`;
          return (
            <div key={court.court_id} className="card" style={{ background: bg }}>
              <p className="font-semibold">{court.court_name}</p>
              <p className="text-sm">Backlog Ratio: {(court.backlog_ratio * 100).toFixed(1)}%</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
