import { OpportunityCard } from "@/components/OpportunityCard";
import { api } from "@/lib/api";

export default async function OpportunitiesPage() {
  const opportunities = await api.getOpportunities().catch(() => []);

  return (
    <div>
      <h2 className="mb-3 text-xl font-semibold text-ink">Opportunities</h2>
      <div className="grid gap-4">
        {opportunities.map((item) => (
          <OpportunityCard key={item.id} item={item} />
        ))}
        {opportunities.length === 0 && <div className="card text-sm text-slate-600">No opportunities yet. Run POST /api/search/run to populate results.</div>}
      </div>
    </div>
  );
}
