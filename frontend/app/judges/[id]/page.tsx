import { getJSON } from "@/components/api";

type JudgeStats = {
  judge_id: number;
  judge_name: string;
  total_hearings: number;
  adjournment_rate: number;
  median_disposal_days: number;
};

export default async function JudgePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const stats = await getJSON<JudgeStats>(`/judges/${id}/stats`).catch(() => null);

  if (!stats) {
    return <p>Judge not found.</p>;
  }

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">{stats.judge_name}</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="card">
          <p className="text-sm">Adjournment Rate</p>
          <p className="font-display text-3xl">{(stats.adjournment_rate * 100).toFixed(1)}%</p>
        </div>
        <div className="card">
          <p className="text-sm">Median Time to Disposal</p>
          <p className="font-display text-3xl">{stats.median_disposal_days}</p>
        </div>
        <div className="card">
          <p className="text-sm">Total Hearings</p>
          <p className="font-display text-3xl">{stats.total_hearings}</p>
        </div>
      </div>
    </div>
  );
}
