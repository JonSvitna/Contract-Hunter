import { SourceTable } from "@/components/SourceTable";
import { api } from "@/lib/api";

export default async function SourcesPage() {
  const sources = await api.getSources().catch(() => []);

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-semibold text-ink">Target Sources</h2>
      <p className="text-sm text-slate-600">Maryland local sources are primary. eMMA is included as a secondary source.</p>
      <SourceTable sources={sources} />
    </div>
  );
}
