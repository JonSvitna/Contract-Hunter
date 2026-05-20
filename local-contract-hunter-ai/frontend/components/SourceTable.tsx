import { Source } from "@/lib/types";

export function SourceTable({ sources }: { sources: Source[] }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[700px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="py-2">Source</th>
            <th className="py-2">Type</th>
            <th className="py-2">Delay</th>
            <th className="py-2">Status</th>
            <th className="py-2">URL</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.id} className="border-b border-slate-100 align-top">
              <td className="py-2 font-medium text-ink">{source.name}</td>
              <td className="py-2 text-slate-700">{source.source_type}</td>
              <td className="py-2 text-slate-700">{source.search_delay_seconds}s</td>
              <td className="py-2 text-slate-700">{source.active ? "Active" : "Paused"}</td>
              <td className="py-2 text-slate-700">
                <a className="underline" href={source.url} target="_blank" rel="noreferrer">
                  Open
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
