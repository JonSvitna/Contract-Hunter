"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { EmmaExcelImportResult } from "@/lib/types";

const DEFAULT_WORKBOOK_PATH = "../../docs/superpowers/emma_docs/Public_Solicitations.xlsx";

export function EmmaExcelImportPanel() {
  const router = useRouter();
  const [path, setPath] = useState(DEFAULT_WORKBOOK_PATH);
  const [autoScore, setAutoScore] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<EmmaExcelImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleImport() {
    const workbookPath = path.trim();
    if (!workbookPath) {
      setError("Enter the local path to the eMMA Excel workbook.");
      return;
    }

    setIsImporting(true);
    setError(null);
    setResult(null);
    try {
      const importResult = await api.importEmmaExcel(workbookPath, autoScore);
      setResult(importResult);
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
        Load the exported eMMA workbook, skip duplicates, and score new matches for the dashboard.
      </p>

      <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="emma-workbook-path">
        Workbook path
      </label>
      <input
        id="emma-workbook-path"
        value={path}
        onChange={(event) => setPath(event.target.value)}
        className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 outline-none focus:border-navy"
      />

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
        {isImporting ? "Importing..." : "Import and score"}
      </button>

      {result && (
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Rows read</div>
            <div className="text-lg font-semibold text-ink">{result.rows_seen}</div>
          </div>
          <div className="rounded-lg bg-emerald-50 p-3">
            <div className="text-xs text-emerald-700">Created</div>
            <div className="text-lg font-semibold text-emerald-900">{result.created}</div>
          </div>
          <div className="rounded-lg bg-amber-50 p-3">
            <div className="text-xs text-amber-700">Skipped</div>
            <div className="text-lg font-semibold text-amber-900">{result.duplicates_skipped}</div>
          </div>
          <div className="rounded-lg bg-blue-50 p-3">
            <div className="text-xs text-blue-700">Scored</div>
            <div className="text-lg font-semibold text-blue-900">{result.scored}</div>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </section>
  );
}
