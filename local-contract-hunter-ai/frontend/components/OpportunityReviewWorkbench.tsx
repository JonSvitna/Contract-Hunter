"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { OpportunityCard } from "@/components/OpportunityCard";
import { api } from "@/lib/api";
import { OpportunitySearchParams, OpportunitySearchResult } from "@/lib/types";

const STATUS_OPTIONS = ["Saved", "Watch", "Pursue", "Skipped"];
const RECOMMENDATION_OPTIONS = ["Pursue", "Watch", "Skip", "Manual Review"];
const SOURCE_STATUS_OPTIONS = ["Open", "Closed"];
const SORT_OPTIONS = [
  { label: "Newest", sort: "created_at", direction: "desc" },
  { label: "Recently updated", sort: "updated_at", direction: "desc" },
  { label: "Due soon", sort: "due_date", direction: "asc" },
  { label: "Fit score", sort: "fit_score", direction: "desc" },
  { label: "Agency", sort: "agency", direction: "asc" },
  { label: "Confidence", sort: "confidence", direction: "desc" }
] as const;

function values(searchParams: URLSearchParams, key: string): string[] {
  return searchParams
    .getAll(key)
    .flatMap((value) => value.split(","))
    .map((value) => value.trim())
    .filter(Boolean);
}

function numberValue(searchParams: URLSearchParams, key: string): number | undefined {
  const raw = searchParams.get(key);
  if (!raw) return undefined;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function paramsFromSearch(searchParams: URLSearchParams): OpportunitySearchParams {
  return {
    page: numberValue(searchParams, "page") || 1,
    page_size: numberValue(searchParams, "page_size") || 25,
    q: searchParams.get("q") || undefined,
    bpm_id: searchParams.get("bpm_id") || undefined,
    agency: searchParams.get("agency") || undefined,
    source: searchParams.get("source") || undefined,
    status: values(searchParams, "status"),
    recommendation: values(searchParams, "recommendation"),
    source_status: values(searchParams, "source_status"),
    manual_review: searchParams.get("manual_review") ? searchParams.get("manual_review") === "true" : undefined,
    due_from: searchParams.get("due_from") || undefined,
    due_to: searchParams.get("due_to") || undefined,
    created_from: searchParams.get("created_from") || undefined,
    created_to: searchParams.get("created_to") || undefined,
    min_confidence: numberValue(searchParams, "min_confidence"),
    max_confidence: numberValue(searchParams, "max_confidence"),
    min_fit_score: numberValue(searchParams, "min_fit_score"),
    max_fit_score: numberValue(searchParams, "max_fit_score"),
    min_skill_match: numberValue(searchParams, "min_skill_match"),
    min_solo_fit: numberValue(searchParams, "min_solo_fit"),
    min_revenue_fit: numberValue(searchParams, "min_revenue_fit"),
    min_local_fit: numberValue(searchParams, "min_local_fit"),
    max_deadline_risk: numberValue(searchParams, "max_deadline_risk"),
    max_complexity_risk: numberValue(searchParams, "max_complexity_risk"),
    sort: searchParams.get("sort") || "created_at",
    direction: (searchParams.get("direction") as "asc" | "desc" | null) || "desc"
  };
}

function cleanParams(params: OpportunitySearchParams): OpportunitySearchParams {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null && value !== "";
    })
  ) as OpportunitySearchParams;
}

function dateInDays(days: number) {
  return new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
}

export function OpportunityReviewWorkbench() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useMemo(() => paramsFromSearch(searchParams), [searchParams]);
  const [draft, setDraft] = useState(params);
  const [result, setResult] = useState<OpportunitySearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(params);
    setLoading(true);
    setError(null);
    api.searchOpportunities(cleanParams(params))
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load opportunities."))
      .finally(() => setLoading(false));
  }, [params]);

  function pushParams(next: OpportunitySearchParams) {
    const cleaned = cleanParams(next);
    const query = new URLSearchParams();
    Object.entries(cleaned).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => query.append(key, item));
        return;
      }
      query.set(key, String(value));
    });
    router.push(`/opportunities${query.toString() ? `?${query.toString()}` : ""}`);
  }

  function applyFilters() {
    pushParams({ ...draft, page: 1 });
  }

  function clearFilters() {
    pushParams({ page: 1, page_size: draft.page_size || 25, sort: "created_at", direction: "desc" });
  }

  function toggleMulti(key: "status" | "recommendation" | "source_status", value: string) {
    const current = draft[key] || [];
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
    setDraft({ ...draft, [key]: next });
  }

  function clearOne(key: string) {
    pushParams({ ...params, [key]: undefined, page: 1 });
  }

  function setPage(page: number) {
    pushParams({ ...params, page });
  }

  const activeFilters = Object.entries(cleanParams(params)).filter(
    ([key]) => !["page", "page_size", "sort", "direction"].includes(key)
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-ink">Opportunities</h2>
          <p className="mt-1 text-sm text-slate-600">
            {result ? `${result.total} matching opportunities` : "Loading opportunities..."}
          </p>
        </div>
        <button onClick={clearFilters} className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">
          Clear filters
        </button>
      </div>

      <section className="card space-y-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px_180px]">
          <label className="text-sm font-medium text-slate-700">
            Search
            <input
              value={draft.q || ""}
              onChange={(event) => setDraft({ ...draft, q: event.target.value })}
              placeholder="Title, agency, source, description, BPM ID"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Sort
            <select
              value={`${draft.sort || "created_at"}:${draft.direction || "desc"}`}
              onChange={(event) => {
                const [sort, direction] = event.target.value.split(":");
                pushParams({ ...params, sort, direction: direction as "asc" | "desc", page: 1 });
              }}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.label} value={`${option.sort}:${option.direction}`}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Page size
            <select
              value={draft.page_size || 25}
              onChange={(event) => pushParams({ ...params, page_size: Number(event.target.value), page: 1 })}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          {["Pursue", "Watch"].map((value) => (
            <button key={value} onClick={() => pushParams({ ...params, recommendation: [value], page: 1 })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{value}</button>
          ))}
          <button onClick={() => pushParams({ ...params, due_to: dateInDays(14), page: 1 })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">Due soon</button>
          <button onClick={() => pushParams({ ...params, manual_review: true, page: 1 })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">Manual review</button>
          <button onClick={() => pushParams({ ...params, source: "Maryland eMMA", source_status: ["Open"], page: 1 })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">eMMA open</button>
        </div>

        <details className="rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-ink">Advanced filters</summary>
          <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <label className="text-xs text-slate-600">BPM ID<input value={draft.bpm_id || ""} onChange={(e) => setDraft({ ...draft, bpm_id: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Agency<input value={draft.agency || ""} onChange={(e) => setDraft({ ...draft, agency: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Source<input value={draft.source || ""} onChange={(e) => setDraft({ ...draft, source: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Due from<input type="date" value={draft.due_from || ""} onChange={(e) => setDraft({ ...draft, due_from: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Due to<input type="date" value={draft.due_to || ""} onChange={(e) => setDraft({ ...draft, due_to: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Min fit score<input type="number" value={draft.min_fit_score ?? ""} onChange={(e) => setDraft({ ...draft, min_fit_score: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Max fit score<input type="number" value={draft.max_fit_score ?? ""} onChange={(e) => setDraft({ ...draft, max_fit_score: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Min confidence<input type="number" min="0" max="1" step="0.05" value={draft.min_confidence ?? ""} onChange={(e) => setDraft({ ...draft, min_confidence: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Max deadline risk<input type="number" value={draft.max_deadline_risk ?? ""} onChange={(e) => setDraft({ ...draft, max_deadline_risk: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Max complexity risk<input type="number" value={draft.max_complexity_risk ?? ""} onChange={(e) => setDraft({ ...draft, max_complexity_risk: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <FilterButtonGroup label="Workflow status" options={STATUS_OPTIONS} selected={draft.status || []} onToggle={(value) => toggleMulti("status", value)} />
            <FilterButtonGroup label="Recommendation" options={RECOMMENDATION_OPTIONS} selected={draft.recommendation || []} onToggle={(value) => toggleMulti("recommendation", value)} />
            <FilterButtonGroup label="eMMA source status" options={SOURCE_STATUS_OPTIONS} selected={draft.source_status || []} onToggle={(value) => toggleMulti("source_status", value)} />
          </div>
        </details>

        <div className="flex flex-wrap gap-2">
          <button onClick={applyFilters} className="rounded-md bg-navy px-3 py-2 text-sm font-medium text-white">Apply filters</button>
          {activeFilters.map(([key, value]) => (
            <button key={key} onClick={() => clearOne(key)} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
              Clear {key}: {Array.isArray(value) ? value.join(", ") : String(value)}
            </button>
          ))}
        </div>
      </section>

      {error && <div className="card border-red-200 bg-red-50 text-sm text-red-700">{error}</div>}
      {loading && <div className="card text-sm text-slate-600">Loading opportunities...</div>}
      {!loading && result && (
        <>
          <div className="grid gap-4">
            {result.items.map((item) => <OpportunityCard key={item.id} item={item} />)}
            {result.items.length === 0 && <div className="card text-sm text-slate-600">No opportunities match these filters.</div>}
          </div>
          <div className="card flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
            <button disabled={result.page <= 1} onClick={() => setPage(result.page - 1)} className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-50">Previous</button>
            <span>Page {result.page} of {result.pages || 1}</span>
            <button disabled={result.pages === 0 || result.page >= result.pages} onClick={() => setPage(result.page + 1)} className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-50">Next</button>
          </div>
        </>
      )}
    </div>
  );
}

function FilterButtonGroup({
  label,
  options,
  selected,
  onToggle
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-slate-600">{label}</div>
      <div className="flex flex-wrap gap-2">
        {options.map((value) => (
          <button
            key={value}
            onClick={() => onToggle(value)}
            className={`rounded-full px-3 py-1 text-xs ${selected.includes(value) ? "bg-navy text-white" : "bg-slate-100 text-slate-700"}`}
          >
            {value}
          </button>
        ))}
      </div>
    </div>
  );
}
