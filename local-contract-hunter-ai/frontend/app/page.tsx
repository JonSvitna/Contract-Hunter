import Link from "next/link";

import { DashboardSummary } from "@/components/DashboardSummary";
import { OpportunityCard } from "@/components/OpportunityCard";
import { api } from "@/lib/api";

export default async function DashboardPage() {
  const opportunities = await api.getOpportunities().catch(() => []);
  const schedulerStatus = await api.getSchedulerStatus().catch(() => null);

  return (
    <div className="space-y-5">
      <section className="card bg-[linear-gradient(130deg,#0b2742,#133b60)] text-white">
        <h2 className="text-xl font-semibold">Local Maryland Contract Intelligence</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-200">
          Focused on county, municipal, school district, library, and utility opportunities suitable for a solo cybersecurity consultancy.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/opportunities" className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-navy">
            Review opportunities
          </Link>
          <Link href="/sources" className="rounded-md border border-white/40 px-3 py-2 text-sm font-semibold text-white">
            Manage sources
          </Link>
        </div>
      </section>

      <DashboardSummary opportunities={opportunities} />

      {schedulerStatus && (
        <section className="card">
          <h3 className="text-base font-semibold text-ink">Automation status</h3>
          <div className="mt-2 grid gap-2 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-4">
            <div>Status: <span className="font-medium">{schedulerStatus.enabled ? "Enabled" : "Disabled"}</span></div>
            <div>Can run now: <span className="font-medium">{schedulerStatus.can_run_now ? "Yes" : "No"}</span></div>
            <div>Reason: <span className="font-medium">{schedulerStatus.reason}</span></div>
            <div>Next run: <span className="font-medium">{schedulerStatus.next_run_at || "Pending"}</span></div>
          </div>
        </section>
      )}

      <section>
        <h3 className="mb-3 text-lg font-semibold text-ink">Top opportunities</h3>
        <div className="grid gap-4">
          {opportunities.slice(0, 6).map((item) => (
            <OpportunityCard key={item.id} item={item} />
          ))}
          {opportunities.length === 0 && <div className="card text-sm text-slate-600">No opportunities found yet. Run search from your backend endpoint.</div>}
        </div>
      </section>
    </div>
  );
}
