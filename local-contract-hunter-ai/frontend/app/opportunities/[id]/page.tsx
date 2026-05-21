"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { ScoreBadge } from "@/components/ScoreBadge";
import { api } from "@/lib/api";
import { Opportunity, ProposalChecklist } from "@/lib/types";

const STATUSES = ["Saved", "Watch", "Pursue", "Skipped"];

function leaningClass(recommendation: ProposalChecklist["bid_recommendation"]) {
  if (recommendation === "Bid") return "bg-emerald-100 text-emerald-800";
  if (recommendation === "Watch") return "bg-amber-100 text-amber-800";
  if (recommendation === "No Bid") return "bg-rose-100 text-rose-800";
  return "bg-slate-100 text-slate-700";
}

export default function OpportunityDetailPage() {
  const params = useParams<{ id: string }>();
  const [item, setItem] = useState<Opportunity | null>(null);
  const [checklist, setChecklist] = useState<ProposalChecklist | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusUpdating, setStatusUpdating] = useState<string | null>(null);
  const [scoring, setScoring] = useState(false);
  const [copiedExternalId, setCopiedExternalId] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getOpportunity(params.id), api.getProposalChecklist(params.id)])
      .then(([nextItem, nextChecklist]) => {
        setItem(nextItem);
        setChecklist(nextChecklist);
      })
      .finally(() => setLoading(false));
  }, [params.id]);

  async function updateStatus(status: string) {
    if (!item) return;
    setStatusUpdating(status);
    setActionError(null);
    try {
      const updated = await api.setStatus(item.id, status);
      setItem(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Status update failed.");
    } finally {
      setStatusUpdating(null);
    }
  }

  async function runScore() {
    if (!item) return;
    setScoring(true);
    setActionError(null);
    try {
      await api.scoreOpportunity(item.id);
      const [refreshed, refreshedChecklist] = await Promise.all([
        api.getOpportunity(item.id),
        api.getProposalChecklist(item.id),
      ]);
      setItem(refreshed);
      setChecklist(refreshedChecklist);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Re-score failed.");
    } finally {
      setScoring(false);
    }
  }

  async function copyExternalId() {
    if (!item?.external_id) return;
    setActionError(null);
    try {
      await navigator.clipboard.writeText(item.external_id);
      setCopiedExternalId(true);
      window.setTimeout(() => setCopiedExternalId(false), 1500);
    } catch {
      setActionError("Could not copy the BPM ID from this browser.");
    }
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
          {item.external_id && (
            <div className="flex flex-wrap items-center gap-2">
              <span>eMMA ID: <span className="font-semibold text-ink">{item.external_id}</span></span>
              <button
                type="button"
                onClick={copyExternalId}
                className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700"
              >
                {copiedExternalId ? "Copied" : "Copy BPM ID"}
              </button>
            </div>
          )}
          <div>Due date: {item.due_date || "Unknown"}</div>
          <div>Current status: {item.status}</div>
          {item.source_status && <div>eMMA source status: {item.source_status}</div>}
          <div>Extraction confidence: {Math.round(item.extraction_confidence * 100)}%</div>
          <div>Manual review needed: {item.manual_review_needed ? "Yes" : "No"}</div>
          <div>eMMA search: <a className="underline" href={item.opportunity_url || item.source_url} target="_blank" rel="noreferrer">Open public solicitations</a></div>
          {item.external_id && <div className="text-xs text-slate-500">Paste the BPM ID into eMMA Public Solicitations search to find the posting.</div>}
          <div>Summary: {item.description_snippet || "No extracted snippet"}</div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {STATUSES.map((status) => (
            <button
              key={status}
              onClick={() => updateStatus(status)}
              disabled={Boolean(statusUpdating) || item.status === status}
              className={`rounded-md border px-3 py-2 text-sm disabled:cursor-not-allowed ${
                item.status === status
                  ? "border-navy bg-navy text-white"
                  : "border-slate-300 text-slate-700 hover:border-navy"
              }`}
            >
              {statusUpdating === status ? "Saving..." : status}
            </button>
          ))}
          <button
            onClick={runScore}
            disabled={scoring}
            className="rounded-md bg-navy px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {scoring ? "Scoring..." : "Re-score"}
          </button>
        </div>
        {actionError && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {actionError}
          </div>
        )}
      </div>

      {checklist && (
        <div className="card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-ink">Proposal checklist</h3>
              <p className="mt-1 text-sm text-slate-700">{checklist.rationale}</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-sm font-semibold ${leaningClass(checklist.bid_recommendation)}`}>
              {checklist.bid_recommendation}
            </span>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div>
              <div className="text-sm font-medium text-ink">Risk flags</div>
              {checklist.risk_flags.length > 0 ? (
                <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                  {checklist.risk_flags.map((flag) => (
                    <li key={flag}>{flag}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-slate-600">No major checklist risks flagged.</p>
              )}
            </div>

            <div>
              <div className="text-sm font-medium text-ink">Verify before bid</div>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                {checklist.checklist_items.map((checklistItem) => (
                  <li key={checklistItem}>{checklistItem}</li>
                ))}
              </ul>
            </div>

            <div>
              <div className="text-sm font-medium text-ink">Next actions</div>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                {checklist.next_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

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
