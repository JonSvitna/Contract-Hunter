import { Opportunity, SchedulerConfig, Source } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {})
    },
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getOpportunities: () => fetchJson<Opportunity[]>("/api/opportunities"),
  getOpportunity: (id: string | number) => fetchJson<Opportunity>(`/api/opportunities/${id}`),
  setStatus: (id: number, status: string) =>
    fetchJson<Opportunity>(`/api/opportunities/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    }),
  scoreOpportunity: (id: number) =>
    fetchJson(`/api/opportunities/${id}/score`, {
      method: "POST"
    }),
  runSearch: () =>
    fetchJson<{ created: number; duplicates_skipped: number; sources: number }>("/api/search/run", {
      method: "POST"
    }),
  getSources: () => fetchJson<Source[]>("/api/sources"),
  getConfigPreview: () => fetchJson<{ business_profile: unknown; keywords: string[] }>("/api/search/config"),
  getSchedulerConfig: () => fetchJson<SchedulerConfig>("/api/scheduler"),
  updateSchedulerConfig: (payload: Partial<SchedulerConfig>) =>
    fetchJson<SchedulerConfig>("/api/scheduler", {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  toggleScheduler: () =>
    fetchJson<SchedulerConfig>("/api/scheduler/toggle", {
      method: "POST"
    })
};
