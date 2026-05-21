"use client";

import Link from "next/link";
import { useState } from "react";

import { Opportunity } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";

export function OpportunityCard({ item }: { item: Opportunity }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const sourceHref = item.opportunity_url || item.source_url;
  const sourceLabel = item.external_id ? "Search on eMMA" : "Open source";

  async function copyExternalId() {
    if (!item.external_id) return;
    try {
      await navigator.clipboard.writeText(item.external_id);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    window.setTimeout(() => setCopyState("idle"), 1500);
  }

  return (
    <div className="card">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-ink">{item.title}</h3>
          <div className="mt-1 text-sm text-slate-600">
            {item.agency} | {item.source_name}
          </div>
        </div>
        <ScoreBadge
          score={item.score?.fit_score}
          recommendation={item.score?.recommendation || "Manual Review"}
        />
      </div>

      <p className="line-clamp-2 text-sm text-slate-700">{item.score?.reasoning || item.description_snippet || "No summary yet."}</p>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-600">
        <span>Status: {item.status}</span>
        <span>Due: {item.due_date || "Unknown"}</span>
        {item.external_id && <span>eMMA ID: <span className="font-semibold text-slate-800">{item.external_id}</span></span>}
        <span>Confidence: {Math.round(item.extraction_confidence * 100)}%</span>
        {item.manual_review_needed && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
            Manual review
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          href={`/opportunities/${item.id}`}
          className="inline-flex rounded-md bg-navy px-3 py-2 text-sm font-medium text-white"
        >
          View details
        </Link>
        {item.external_id && (
          <button
            type="button"
            onClick={copyExternalId}
            className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700"
          >
            {copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : "Copy BPM ID"}
          </button>
        )}
        {sourceHref && (
          <a
            href={sourceHref}
            target="_blank"
            rel="noreferrer"
            className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700"
          >
            {sourceLabel}
          </a>
        )}
      </div>
    </div>
  );
}
