import { SourceTable } from "@/components/SourceTable";
import { api } from "@/lib/api";

export default async function SourcesPage() {
  let loadError: string | null = null;
  const dashboard = await api.getSourceDashboard().catch((error) => {
    loadError = error instanceof Error ? error.message : "Source dashboard data could not load.";
    return { items: [] };
  });

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-semibold text-ink">Source Validation</h2>
      <p className="text-sm text-slate-600">
        Maryland local sources are primary. eMMA is included as a secondary source and workbook imports stay separate.
      </p>
      <SourceTable initialItems={dashboard.items} loadError={loadError} />
    </div>
  );
}
