import { Opportunity } from "@/lib/types";

function stat(label: string, value: number | string) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}

export function DashboardSummary({ opportunities }: { opportunities: Opportunity[] }) {
  const pursue = opportunities.filter((o) => o.score?.recommendation === "Pursue").length;
  const watch = opportunities.filter((o) => o.score?.recommendation === "Watch").length;
  const skipped = opportunities.filter((o) => o.status === "Skipped").length;
  const upcoming = opportunities.filter((o) => {
    if (!o.due_date) return false;
    return new Date(o.due_date).getTime() > Date.now();
  }).length;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {stat("Total Opportunities", opportunities.length)}
      {stat("Strong Pursue", pursue)}
      {stat("Watch", watch)}
      {stat("Skipped", skipped)}
      {stat("Upcoming Deadlines", upcoming)}
    </div>
  );
}
