import Link from "next/link";

import { ScoreBadge } from "@/components/ScoreBadge";
import { DigestPreview } from "@/lib/types";

export function DigestPreviewCard({ preview }: { preview: DigestPreview | null }) {
  return (
    <section className="card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-ink">Daily digest preview</h3>
          <p className="mt-1 text-sm text-slate-600">Read-only preview of today&apos;s highest-fit candidates.</p>
        </div>
        <div className="text-xs text-slate-500">
          {preview ? new Date(preview.generated_at).toLocaleString() : "Unavailable"}
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {preview?.candidates.slice(0, 3).map((candidate) => (
          <div key={candidate.id} className="rounded-md border border-slate-200 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <Link href={`/opportunities/${candidate.id}`} className="text-sm font-semibold text-ink underline-offset-2 hover:underline">
                  {candidate.title}
                </Link>
                <div className="mt-1 text-xs text-slate-600">
                  {candidate.agency} | Due {candidate.due_date || "Unknown"}
                </div>
              </div>
              <ScoreBadge score={candidate.fit_score} recommendation={candidate.recommendation} />
            </div>
            <p className="mt-2 line-clamp-2 text-xs text-slate-600">{candidate.reasoning || "No scoring explanation yet."}</p>
          </div>
        ))}
        {preview && preview.candidates.length === 0 && (
          <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">
            No Pursue or Watch candidates are ready for the digest yet.
          </div>
        )}
        {!preview && <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">Digest preview unavailable.</div>}
      </div>
    </section>
  );
}
