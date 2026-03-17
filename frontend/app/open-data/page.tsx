import Link from "next/link";

import { getJSON } from "@/components/api";

type DatasetItem = {
  dataset_id: string;
  name: string;
  description: string;
  version: string;
  update_frequency: string;
  privacy_classification: string;
  license: string;
  recommended_citation: string;
};

type CatalogResponse = {
  items: DatasetItem[];
  count: number;
};

type SearchParams = {
  state?: string;
  court?: string;
  case_type?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
  importance_score?: string;
  max_rows?: string;
};

function buildDownloadUrl(datasetId: string, format: string, searchParams: SearchParams): string {
  const params = new URLSearchParams();
  params.set("format", format);

  const keys: Array<keyof SearchParams> = [
    "state",
    "court",
    "case_type",
    "date_from",
    "date_to",
    "status",
    "importance_score",
    "max_rows",
  ];

  for (const key of keys) {
    const value = searchParams[key];
    if (value && value.trim()) {
      params.set(key, value.trim());
    }
  }

  return `/api/v1/datasets/${datasetId}/download?${params.toString()}`;
}

export default async function OpenDataPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const filters = await searchParams;
  const catalog = await getJSON<CatalogResponse>("/datasets").catch(() => ({ items: [], count: 0 }));

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Open Data Catalog</h1>
        <p className="max-w-3xl text-sm text-ink/75">
          Download machine-readable datasets from Court Case Delay &amp; Justice Tracker with reproducible versions,
          data dictionaries, and privacy safeguards.
        </p>
      </header>

      <section className="card space-y-4">
        <h2 className="font-display text-xl">Filter Interface</h2>
        <form className="grid gap-3 md:grid-cols-4" method="GET">
          <input name="state" defaultValue={filters.state} placeholder="State" className="rounded-lg border border-ink/20 px-3 py-2" />
          <input name="court" defaultValue={filters.court} placeholder="Court" className="rounded-lg border border-ink/20 px-3 py-2" />
          <input name="case_type" defaultValue={filters.case_type} placeholder="Case Type" className="rounded-lg border border-ink/20 px-3 py-2" />
          <input name="status" defaultValue={filters.status} placeholder="Status" className="rounded-lg border border-ink/20 px-3 py-2" />
          <input name="date_from" defaultValue={filters.date_from} type="date" className="rounded-lg border border-ink/20 px-3 py-2" />
          <input name="date_to" defaultValue={filters.date_to} type="date" className="rounded-lg border border-ink/20 px-3 py-2" />
          <input
            name="importance_score"
            defaultValue={filters.importance_score}
            placeholder="Min Importance (0-1)"
            className="rounded-lg border border-ink/20 px-3 py-2"
          />
          <input
            name="max_rows"
            defaultValue={filters.max_rows ?? "100000"}
            placeholder="Max Rows"
            className="rounded-lg border border-ink/20 px-3 py-2"
          />
          <button className="rounded-lg bg-ocean px-4 py-2 text-sm font-semibold text-white">Apply Filters</button>
        </form>
      </section>

      <section className="grid gap-4">
        {catalog.items.map((dataset) => (
          <article key={dataset.dataset_id} className="card space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-display text-lg">{dataset.name}</h3>
              <span className="rounded-full bg-ink/5 px-3 py-1 text-xs uppercase tracking-wide">v{dataset.version}</span>
            </div>
            <p className="text-sm text-ink/75">{dataset.description}</p>
            <div className="grid gap-2 text-xs text-ink/80 md:grid-cols-3">
              <div>
                <strong>Update:</strong> {dataset.update_frequency}
              </div>
              <div>
                <strong>Privacy:</strong> {dataset.privacy_classification}
              </div>
              <div>
                <strong>License:</strong> {dataset.license}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-sm">
              <a className="rounded-lg bg-accent px-3 py-2 text-white" href={buildDownloadUrl(dataset.dataset_id, "csv", filters)}>
                Download CSV
              </a>
              <a className="rounded-lg bg-ocean px-3 py-2 text-white" href={buildDownloadUrl(dataset.dataset_id, "json", filters)}>
                Download JSON
              </a>
              <a className="rounded-lg bg-ink px-3 py-2 text-white" href={buildDownloadUrl(dataset.dataset_id, "parquet", filters)}>
                Download Parquet
              </a>
              <a className="rounded-lg border border-ink/30 px-3 py-2" href={buildDownloadUrl(dataset.dataset_id, "ndjson", filters)}>
                Stream NDJSON
              </a>
              <a className="rounded-lg border border-ink/30 px-3 py-2" href={`/api/v1/datasets/${dataset.dataset_id}/schema`}>
                Schema
              </a>
              <a className="rounded-lg border border-ink/30 px-3 py-2" href={`/api/v1/datasets/${dataset.dataset_id}`}>
                Documentation
              </a>
            </div>
            <p className="text-xs text-ink/60">Recommended citation: {dataset.recommended_citation}</p>
          </article>
        ))}
        {catalog.count === 0 ? <div className="card text-sm">No datasets available at this time.</div> : null}
      </section>

      <footer className="card text-sm text-ink/70">
        Need reproducible snapshots? Use versioned endpoints like
        <span className="mx-1 font-mono">/api/v1/datasets/case_metadata/v/1.0.0</span>
        and cite retrieval dates in published work.
      </footer>

      <div>
        <Link href="/" className="text-sm text-ocean underline">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
