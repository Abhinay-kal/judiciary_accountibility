import { Timeline } from "@/components/Timeline";
import { getJSON } from "@/components/api";

type CaseData = {
  id: number;
  case_number: string;
  status: string;
  source_url: string;
};

type Hearing = {
  id: number;
  date: string;
  outcome_text?: string;
  source: string;
};

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [caseData, hearings] = await Promise.all([
    getJSON<CaseData>(`/cases/${id}`).catch(() => null),
    getJSON<Hearing[]>(`/cases/${id}/timeline`).catch(() => [])
  ]);

  if (!caseData) {
    return <p>Case not found.</p>;
  }

  return (
    <div className="space-y-5">
      <section className="card">
        <h1 className="font-display text-3xl">{caseData.case_number}</h1>
        <p className="text-sm text-ink/70">Status: {caseData.status}</p>
        <a href={caseData.source_url} className="text-sm text-clay underline">
          Official source
        </a>
      </section>

      <section>
        <h2 className="mb-3 font-display text-2xl">Timeline</h2>
        <Timeline hearings={hearings} />
      </section>
    </div>
  );
}
