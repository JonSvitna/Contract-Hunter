"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { SearchRunResult, SourceDashboardItem } from "@/lib/types";

type SourceTableProps = {
  initialItems: SourceDashboardItem[];
  loadError?: string | null;
};

function relativeTime(value?: string | null): string {
  if (!value) return "Never";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "Unknown";
  const diffSeconds = Math.round((timestamp - Date.now()) / 1000);
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, secondsPerUnit] of units) {
    if (Math.abs(diffSeconds) >= secondsPerUnit) {
      return formatter.format(Math.round(diffSeconds / secondsPerUnit), unit);
    }
  }
  return formatter.format(diffSeconds, "second");
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function runTone(source: SourceDashboardItem): string {
  const run = source.last_run;
  if (!source.active) return "bg-slate-50 text-slate-500";
  if (!run) return "bg-white";
  if (run.status === "failed") return "bg-red-50";
  if (run.status === "completed" && run.candidates_found > 0 && run.manual_review_fallback_rate >= 0.8) {
    return "bg-amber-50";
  }
  return "bg-white";
}

function resultMessage(result: SearchRunResult): string {
  return `${result.created ?? 0} created, ${result.duplicates_skipped ?? 0} duplicates skipped, ${result.scored ?? 0} scored.`;
}

export function SourceTable({ initialItems, loadError }: SourceTableProps) {
  const [items, setItems] = useState(initialItems);
  const [validatingId, setValidatingId] = useState<number | null>(null);
  const [runningSamGov, setRunningSamGov] = useState(false);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const [rowMessages, setRowMessages] = useState<Record<number, string>>({});

  const summary = useMemo(() => {
    return {
      total: items.length,
      active: items.filter((source) => source.active).length,
      neverRun: items.filter((source) => !source.last_run).length,
      failed: items.filter((source) => source.last_run?.status === "failed").length,
      highManualReview: items.filter((source) => {
        const run = source.last_run;
        return Boolean(run && run.candidates_found > 0 && run.manual_review_fallback_rate >= 0.8);
      }).length,
    };
  }, [items]);

  async function runSamGov(source: SourceDashboardItem) {
    setRunningSamGov(true);
    setRowErrors((current) => ({ ...current, [source.id]: "" }));
    setRowMessages((current) => ({ ...current, [source.id]: "" }));
    try {
      const result = await api.runSamGov();
      setRowMessages((current) => ({ ...current, [source.id]: resultMessage(result) }));
      const refreshed = await api.getSourceDashboard();
      setItems(refreshed.items);
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [source.id]: error instanceof Error ? error.message : "SAM.gov run failed.",
      }));
    } finally {
      setRunningSamGov(false);
    }
  }

  async function validateSource(source: SourceDashboardItem) {
    setValidatingId(source.id);
    setRowErrors((current) => ({ ...current, [source.id]: "" }));
    setRowMessages((current) => ({ ...current, [source.id]: "" }));
    try {
      const result = await api.validateSource(source.name, true);
      setRowMessages((current) => ({ ...current, [source.id]: resultMessage(result) }));
      const refreshed = await api.getSourceDashboard();
      setItems(refreshed.items);
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [source.id]: error instanceof Error ? error.message : "Validation failed.",
      }));
    } finally {
      setValidatingId(null);
    }
  }

  return (
    <div className="space-y-3">
      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {loadError}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="card">
          <div className="text-xs text-slate-500">Total sources</div>
          <div className="mt-1 text-2xl font-semibold text-ink">{summary.total}</div>
        </div>
        <div className="card">
          <div className="text-xs text-slate-500">Active</div>
          <div className="mt-1 text-2xl font-semibold text-ink">{summary.active}</div>
        </div>
        <div className="card">
          <div className="text-xs text-slate-500">Never run</div>
          <div className="mt-1 text-2xl font-semibold text-ink">{summary.neverRun}</div>
        </div>
        <div className="card">
          <div className="text-xs text-slate-500">Failed last run</div>
          <div className="mt-1 text-2xl font-semibold text-red-700">{summary.failed}</div>
        </div>
        <div className="card">
          <div className="text-xs text-slate-500">High manual review</div>
          <div className="mt-1 text-2xl font-semibold text-amber-700">{summary.highManualReview}</div>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[1100px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2 pr-3">Source</th>
              <th className="py-2 pr-3">Type</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3">Last run</th>
              <th className="py-2 pr-3">Run result</th>
              <th className="py-2 pr-3">Candidates</th>
              <th className="py-2 pr-3">Created / duplicate / scored</th>
              <th className="py-2 pr-3">Manual review</th>
              <th className="py-2 pr-3">Error</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((source) => {
              const run = source.last_run;
              const canValidate = source.active && source.source_type.toLowerCase() === "generic";
              const isSamGov = source.source_type.toLowerCase() === "samgov";
              return (
                <tr key={source.id} className={`border-b border-slate-100 align-top ${runTone(source)}`}>
                  <td className="py-3 pr-3">
                    <div className="font-medium text-ink">{source.name}</div>
                    {source.notes && <div className="mt-1 text-xs text-slate-500">{source.notes}</div>}
                    <a className="mt-1 inline-block text-xs underline" href={source.url} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                    {rowMessages[source.id] && (
                      <div className="mt-2 rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-800">
                        {rowMessages[source.id]}
                      </div>
                    )}
                    {rowErrors[source.id] && (
                      <div className="mt-2 rounded-md bg-red-50 px-2 py-1 text-xs text-red-700">
                        {rowErrors[source.id]}
                      </div>
                    )}
                  </td>
                  <td className="py-3 pr-3 text-slate-700">{source.source_type}</td>
                  <td className="py-3 pr-3 text-slate-700">{source.active ? "Active" : "Paused"}</td>
                  <td className="py-3 pr-3 text-slate-700">{relativeTime(run?.started_at)}</td>
                  <td className="py-3 pr-3">
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                      {run?.status ?? "Never"}
                    </span>
                  </td>
                  <td className="py-3 pr-3 text-slate-700">{run?.candidates_found ?? "-"}</td>
                  <td className="py-3 pr-3 text-slate-700">
                    {run ? `${run.created} / ${run.duplicates_skipped} / ${run.scored}` : "-"}
                  </td>
                  <td className="py-3 pr-3 text-slate-700">
                    {run ? `${formatPercent(run.manual_review_fallback_rate)} (${run.manual_review_created} created)` : "-"}
                  </td>
                  <td className="max-w-[220px] py-3 pr-3 text-xs text-red-700">
                    {run?.status === "failed" ? run.error_message : ""}
                  </td>
                  <td className="py-3">
                    {canValidate ? (
                      <button
                        type="button"
                        onClick={() => validateSource(source)}
                        disabled={validatingId === source.id}
                        className="rounded-md bg-navy px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                      >
                        {validatingId === source.id ? "Validating..." : "Validate"}
                      </button>
                    ) : isSamGov ? (
                      <button
                        type="button"
                        onClick={() => runSamGov(source)}
                        disabled={runningSamGov}
                        className="rounded-md bg-sage px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                      >
                        {runningSamGov ? "Running..." : "Run SAM.gov"}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-500">Not available</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={10} className="py-6 text-center text-sm text-slate-600">
                  No sources found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
