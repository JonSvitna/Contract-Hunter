type Props = {
  score?: number;
  recommendation?: string;
};

export function ScoreBadge({ score, recommendation }: Props) {
  const bg =
    recommendation === "Pursue"
      ? "bg-emerald-100 text-emerald-800"
      : recommendation === "Watch"
        ? "bg-amber-100 text-amber-800"
        : recommendation === "Skip"
          ? "bg-rose-100 text-rose-800"
          : "bg-slate-100 text-slate-700";

  return (
    <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${bg}`}>
      <span>{recommendation || "Manual Review"}</span>
      <span>{typeof score === "number" ? `${score}` : "-"}</span>
    </div>
  );
}
