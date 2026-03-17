import { CorrectionRequestForm } from "@/components/CorrectionRequestForm";
import { EvidenceBadge } from "@/components/EvidenceBadge";
import { PublicNoteRenderer } from "@/components/PublicNoteRenderer";
import { Timeline } from "@/components/Timeline";
import { getJSON } from "@/components/api";
import { OfficialResponsesPanel } from "./components/OfficialResponsesPanel";
import { SubmitOfficialResponseForm } from "./components/SubmitOfficialResponseForm";

type CaseData = {
  id: number;
  case_number: string;
  status: string;
  source_url: string;
  plain_summary_short?: string;
  plain_summary_detailed?: string;
  summary_confidence?: number;
  impact_headline?: string;
  impact_summary?: string;
  impact_confidence?: number;
  impact_content?: {
    key_takeaways?: string[];
    why_it_matters?: string;
    impact_statement?: string;
    calls_to_action?: string[];
    journalist_quote?: string;
    policymaker_note?: string;
    credibility_notes?: {
      last_updated?: string | null;
      methodology_reference?: string;
    };
  };
  plain_summary?: {
    bullet_points?: string[];
    confidence_note?: string | null;
    key_metrics_used?: string[];
  };
  public_status?: "PUBLIC" | "LIMITED" | "HIDDEN";
  public_note?: string;
  dormancy_status?: string;
  dormancy_score?: number;
  last_activity_date?: string;
  days_since_last_activity?: number;
  moderation_render_meta?: {
    labels?: string[];
    parser_confidence?: number;
    source_links?: string[];
  };
};

type DormancyPayload = {
  status?: string;
  severity?: string;
  dormancy_score?: number;
  explanation?: string;
  timeline_marker?: string;
  last_activity_date?: string;
  days_since_last_activity?: number;
};

type CaseProvenance = {
  fields?: Record<
    string,
    Array<{
      source_name?: string;
      source_type?: string;
      source_url?: string;
      fetch_time?: string;
      confidence_score?: number;
      is_primary_source?: boolean;
    }>
  >;
};

type Hearing = {
  id: number;
  date: string;
  outcome_text?: string;
  source: string;
};

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [caseData, hearings, provenance] = await Promise.all([
    getJSON<CaseData>(`/cases/${id}`).catch(() => null),
    getJSON<Hearing[]>(`/cases/${id}/timeline`).catch(() => []),
    getJSON<CaseProvenance>(`/cases/${id}/provenance`).catch(() => null)
  ]);

  const dormancy = await getJSON<DormancyPayload>(`/cases/${id}/dormancy`).catch(() => null);

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
        <div className="mt-3">
          <EvidenceBadge
            label={caseData.moderation_render_meta?.labels?.includes("VERIFIED") ? "Verified" : "Requires verification"}
            confidence={caseData.moderation_render_meta?.parser_confidence}
            explanation="Label generated from source evidence confidence and moderation safeguards."
            provenanceLinks={caseData.moderation_render_meta?.source_links || [caseData.source_url]}
          />
        </div>
        <div className="mt-3">
          <PublicNoteRenderer
            publicStatus={caseData.public_status}
            publicNote={caseData.public_note}
            contact="moderation@justice-tracker.org"
          />
        </div>

        {dormancy?.status === "dormant" && (
          <div className="mt-4 rounded-xl border border-orange-300 bg-orange-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="rounded-full bg-orange-200 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-orange-900">
                Dormant case
              </span>
              <span className="text-xs text-orange-900/80">
                Score: {typeof dormancy.dormancy_score === "number" ? dormancy.dormancy_score.toFixed(2) : "N/A"}
              </span>
            </div>
            {dormancy.explanation && <p className="mt-2 text-sm text-orange-950">{dormancy.explanation}</p>}
            <div className="mt-2 text-xs text-orange-900/80">
              {dormancy.timeline_marker || "Dormancy signal is based on prolonged inactivity relative to similar cases."}
            </div>
            {(dormancy.last_activity_date || typeof dormancy.days_since_last_activity === "number") && (
              <div className="mt-1 text-xs text-orange-900/80">
                Last activity: {dormancy.last_activity_date || "N/A"}
                {typeof dormancy.days_since_last_activity === "number" ? ` (${dormancy.days_since_last_activity} days ago)` : ""}
              </div>
            )}
          </div>
        )}

        {(caseData.plain_summary_short || caseData.plain_summary_detailed) && (
          <div className="mt-4 rounded-xl border border-clay/30 bg-clay/10 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-xl">Plain-English Summary</h2>
              <span
                className="text-xs text-ink/70"
                title="Higher confidence means stronger comparable-data coverage and more stable analytics signals."
              >
                Confidence: {typeof caseData.summary_confidence === "number" ? caseData.summary_confidence.toFixed(2) : "N/A"}
              </span>
            </div>
            <p className="mt-2 text-sm text-ink/90">{caseData.plain_summary_short}</p>
            {caseData.plain_summary?.bullet_points && caseData.plain_summary.bullet_points.length > 0 && (
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink/85">
                {caseData.plain_summary.bullet_points.slice(0, 4).map((point, idx) => (
                  <li key={`${idx}-${point.slice(0, 16)}`}>{point}</li>
                ))}
              </ul>
            )}
            {caseData.plain_summary?.confidence_note && (
              <p className="mt-3 text-xs text-ink/70">{caseData.plain_summary.confidence_note}</p>
            )}
          </div>
        )}

        {(caseData.impact_headline || caseData.impact_summary || caseData.impact_content?.journalist_quote) && (
          <div className="mt-4 space-y-3 rounded-xl border border-ink/10 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-display text-xl">Impact Brief</h2>
              <div className="text-xs text-ink/70">
                Confidence: {typeof caseData.impact_confidence === "number" ? caseData.impact_confidence.toFixed(2) : "N/A"}
              </div>
            </div>

            {caseData.impact_headline && (
              <div className="rounded-lg border border-amber-300/60 bg-amber-50 p-3">
                <p className="text-sm font-semibold text-ink">{caseData.impact_headline}</p>
              </div>
            )}

            {caseData.impact_summary && <p className="text-sm text-ink/90">{caseData.impact_summary}</p>}

            {caseData.impact_content?.journalist_quote && (
              <blockquote className="rounded-lg border-l-4 border-clay bg-clay/10 px-4 py-3 text-sm italic text-ink/90">
                &ldquo;{caseData.impact_content.journalist_quote}&rdquo;
              </blockquote>
            )}

            {caseData.impact_content?.key_takeaways && caseData.impact_content.key_takeaways.length > 0 && (
              <div className="rounded-lg border border-ink/10 p-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink/70">Key Takeaways</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/85">
                  {caseData.impact_content.key_takeaways.slice(0, 4).map((point, idx) => (
                    <li key={`${idx}-${point.slice(0, 16)}`}>{point}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid gap-3 md:grid-cols-2">
              {caseData.impact_content?.why_it_matters && (
                <div className="rounded-lg border border-ink/10 p-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink/70">Why It Matters</h3>
                  <p className="mt-1 text-sm text-ink/85">{caseData.impact_content.why_it_matters}</p>
                </div>
              )}
              {caseData.impact_content?.impact_statement && (
                <div className="rounded-lg border border-ink/10 p-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink/70">Impact Statement</h3>
                  <p className="mt-1 text-sm text-ink/85">{caseData.impact_content.impact_statement}</p>
                </div>
              )}
            </div>

            {caseData.impact_content?.calls_to_action && caseData.impact_content.calls_to_action.length > 0 && (
              <div className="rounded-lg border border-ink/10 p-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink/70">Suggested Actions</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/85">
                  {caseData.impact_content.calls_to_action.slice(0, 4).map((action, idx) => (
                    <li key={`${idx}-${action.slice(0, 16)}`}>{action}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex flex-wrap gap-3 text-xs text-ink/70">
              {caseData.impact_content?.credibility_notes?.last_updated && (
                <span>Updated: {new Date(caseData.impact_content.credibility_notes.last_updated).toLocaleDateString()}</span>
              )}
              {caseData.impact_content?.credibility_notes?.methodology_reference && (
                <span>{caseData.impact_content.credibility_notes.methodology_reference}</span>
              )}
            </div>

            <div>
              <a
                href={`/investigation/${caseData.id}/export/pdf`}
                className="inline-flex rounded-md border border-clay/40 bg-clay/10 px-3 py-2 text-xs font-medium text-ink hover:bg-clay/20"
              >
                Download Brief (PDF)
              </a>
            </div>
          </div>
        )}

        {provenance?.fields && Object.keys(provenance.fields).length > 0 && (
          <div className="mt-4 rounded-xl border border-ink/10 bg-white p-4 shadow-sm">
            <h2 className="font-display text-xl">Evidence Provenance</h2>
            <p className="mt-1 text-xs text-ink/70">Hover source rows for retrieval details.</p>
            <div className="mt-3 space-y-2">
              {Object.entries(provenance.fields)
                .slice(0, 3)
                .map(([field, records]) => {
                  const primary = records.find((row) => row.is_primary_source) || records[0];
                  if (!primary) return null;
                  const tooltip = `${field} from ${primary.source_name || "unknown source"}${
                    primary.fetch_time ? `, retrieved on ${new Date(primary.fetch_time).toLocaleDateString()}` : ""
                  }`;
                  return (
                    <div key={field} className="rounded-md border border-ink/10 px-3 py-2 text-sm" title={tooltip}>
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-ink">{field.replace(/_/g, " ")}</span>
                        <span className="text-xs text-ink/70">
                          {primary.source_name || "unknown"} ({primary.source_type || "N/A"})
                        </span>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-display text-2xl">Timeline</h2>
        <Timeline hearings={hearings} />
      </section>

      <OfficialResponsesPanel caseId={caseData.id} />
      <SubmitOfficialResponseForm caseId={caseData.id} />

      <CorrectionRequestForm targetType="case" targetId={caseData.id} />
    </div>
  );
}
