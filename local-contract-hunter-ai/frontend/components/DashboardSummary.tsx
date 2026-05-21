import { OpportunitySummary } from "@/lib/types";

function stat(label: string, value: number | string) {
  return (
    <div className="card min-h-[96px]">
      <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}

export function DashboardSummary({ summary }: { summary: OpportunitySummary | null }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {stat("Total Opportunities", summary?.total ?? 0)}
      {stat("Strong Pursue", summary?.pursue ?? 0)}
      {stat("Watch", summary?.watch ?? 0)}
      {stat("Skipped", summary?.skipped ?? 0)}
      {stat("Manual Review", summary?.manual_review ?? 0)}
      {stat("Upcoming Deadlines", summary?.upcoming_deadlines ?? 0)}
    </div>
  );
}
