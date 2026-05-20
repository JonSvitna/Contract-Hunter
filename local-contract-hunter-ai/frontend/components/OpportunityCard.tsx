import Link from "next/link";

import { Opportunity } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";

export function OpportunityCard({ item }: { item: Opportunity }) {
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
        <span>Confidence: {Math.round(item.extraction_confidence * 100)}%</span>
      </div>

      <div className="mt-4">
        <Link
          href={`/opportunities/${item.id}`}
          className="inline-flex rounded-md bg-navy px-3 py-2 text-sm font-medium text-white"
        >
          View details
        </Link>
      </div>
    </div>
  );
}
