"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { EmmaExcelImportResult, ImportRun } from "@/lib/types";

export function EmmaExcelImportPanel() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [autoScore, setAutoScore] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<EmmaExcelImportResult | null>(null);
  const [history, setHistory] = useState<ImportRun[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    const runs = await api.getImportRuns().catch(() => []);
    setHistory(runs);
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  async function handleImport() {
    if (!file) {
      setError("Choose the eMMA .xlsx workbook to upload.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setError("Choose a .xlsx workbook exported from eMMA.");
      return;
    }

    setIsImporting(true);
    setError(null);
    setResult(null);
    try {
      const importResult = await api.uploadEmmaExcel(file, autoScore);
      setResult(importResult);
      await refreshHistory();
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <section className="card h-full">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">eMMA Import</div>
          <h3 className="mt-1 text-base font-semibold text-ink">Import public solicitations</h3>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
          Excel
        </span>
      </div>

      <p className="mt-3 text-sm text-slate-600">
        Upload the exported eMMA workbook, update existing rows, and score new matches for the dashboard.
      </p>

      <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="emma-workbook-file">
        Workbook upload
      </label>
      <input
        id="emma-workbook-file"
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 outline-none file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1 file:text-sm file:font-medium file:text-slate-700 focus:border-navy"
      />
      {file && <div className="mt-1 text-xs text-slate-500">Selected: {file.name}</div>}

      <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={autoScore}
          onChange={(event) => setAutoScore(event.target.checked)}
          className="h-4 w-4 rounded border-slate-300"
        />
        Score new opportunities after import
      </label>

      <button
        type="button"
        onClick={handleImport}
        disabled={isImporting}
        className="mt-4 w-full rounded-md bg-navy px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {isImporting ? "Importing..." : "Upload and import"}
      </button>

      {result && (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <div className="text-sm font-semibold text-emerald-900">Import complete</div>
            <div className="mt-1 text-xs text-emerald-800">
              {result.created} created, {result.updated} updated, {result.unchanged} unchanged, {result.skipped} skipped from {result.source}.
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {[
              ["Rows read", result.rows_seen, "bg-slate-50 text-ink"],
              ["Created", result.created, "bg-emerald-50 text-emerald-900"],
              ["Updated", result.updated, "bg-blue-50 text-blue-900"],
              ["Unchanged", result.unchanged, "bg-slate-50 text-slate-900"],
              ["Skipped", result.skipped, "bg-amber-50 text-amber-900"],
              ["Scored", result.scored, "bg-indigo-50 text-indigo-900"]
            ].map(([label, value, classes]) => (
              <div key={label} className={`rounded-lg p-3 ${classes}`}>
                <div className="text-xs opacity-75">{label}</div>
                <div className="text-lg font-semibold">{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {history.length > 0 && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          <div className="text-sm font-semibold text-ink">Recent imports</div>
          <div className="mt-2 space-y-2">
            {history.slice(0, 3).map((run) => (
              <div key={run.id} className="rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
                <div className="font-medium text-slate-900">{run.filename}</div>
                <div>
                  {run.created} created, {run.updated} updated, {run.unchanged} unchanged, {run.skipped} skipped, {run.scored} scored
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
