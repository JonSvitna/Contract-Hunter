"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { ScoreBadge } from "@/components/ScoreBadge";
import { api } from "@/lib/api";
import { Opportunity } from "@/lib/types";

const STATUSES = ["Saved", "Watch", "Pursue", "Skipped"];

export default function OpportunityDetailPage() {
  const params = useParams<{ id: string }>();
  const [item, setItem] = useState<Opportunity | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getOpportunity(params.id)
      .then(setItem)
      .finally(() => setLoading(false));
  }, [params.id]);

  async function updateStatus(status: string) {
    if (!item) return;
    const updated = await api.setStatus(item.id, status);
    setItem(updated);
  }

  async function runScore() {
    if (!item) return;
    await api.scoreOpportunity(item.id);
    const refreshed = await api.getOpportunity(item.id);
    setItem(refreshed);
  }

  if (loading) return <div className="card">Loading...</div>;
  if (!item) return <div className="card">Opportunity not found.</div>;

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-ink">{item.title}</h2>
            <div className="mt-1 text-sm text-slate-600">
              {item.agency} | {item.source_name}
            </div>
          </div>
          <ScoreBadge score={item.score?.fit_score} recommendation={item.score?.recommendation || "Manual Review"} />
        </div>

        <div className="mt-4 grid gap-2 text-sm text-slate-700">
          <div>Due date: {item.due_date || "Unknown"}</div>
          <div>Current status: {item.status}</div>
          <div>Source URL: <a className="underline" href={item.source_url} target="_blank" rel="noreferrer">Open source</a></div>
          {item.opportunity_url && <div>Opportunity URL: <a className="underline" href={item.opportunity_url} target="_blank" rel="noreferrer">Open posting</a></div>}
          <div>Summary: {item.description_snippet || "No extracted snippet"}</div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {STATUSES.map((status) => (
            <button
              key={status}
              onClick={() => updateStatus(status)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {status}
            </button>
          ))}
          <button onClick={runScore} className="rounded-md bg-navy px-3 py-2 text-sm text-white">
            Re-score
          </button>
        </div>
      </div>

      <div className="card">
        <h3 className="text-base font-semibold text-ink">Score breakdown</h3>
        <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
          <div>Fit score: {item.score?.fit_score ?? "-"}</div>
          <div>Skill match: {item.score?.skill_match ?? "-"}</div>
          <div>Solo fit: {item.score?.solo_fit ?? "-"}</div>
          <div>Revenue fit: {item.score?.revenue_fit ?? "-"}</div>
          <div>Local fit: {item.score?.local_fit ?? "-"}</div>
          <div>Deadline risk: {item.score?.deadline_risk ?? "-"}</div>
          <div>Complexity risk: {item.score?.complexity_risk ?? "-"}</div>
          <div>Past performance risk: {item.score?.past_performance_risk ?? "-"}</div>
        </div>
        <div className="mt-3 text-sm text-slate-700">Reasoning: {item.score?.reasoning || "No scoring explanation yet."}</div>
        <div className="mt-3">
          <div className="text-sm font-medium text-ink">Next steps</div>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
            {(item.score?.next_steps || []).map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
