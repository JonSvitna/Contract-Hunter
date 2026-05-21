import {
  DigestPreview,
  ImportRun,
  Opportunity,
  ProposalChecklist,
  EmmaExcelImportResult,
  SchedulerConfig,
  SchedulerStatus,
  SearchRunResult,
  Source,
  ThrottleConfig,
  ThrottleControl,
} from "@/lib/types";

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
    const errorBody = await res.json().catch(() => null);
    const detail = typeof errorBody?.detail === "string" ? errorBody.detail : null;
    throw new Error(detail || `API error: ${res.status}`);
  }
  return res.json();
}

async function fetchForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store"
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    const detail = typeof errorBody?.detail === "string" ? errorBody.detail : null;
    throw new Error(detail || `API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getOpportunities: () => fetchJson<Opportunity[]>("/api/opportunities"),
  getOpportunity: (id: string | number) => fetchJson<Opportunity>(`/api/opportunities/${id}`),
  getProposalChecklist: (id: string | number) => fetchJson<ProposalChecklist>(`/api/opportunities/${id}/checklist`),
  getDigestPreview: () => fetchJson<DigestPreview>("/api/digest/preview"),
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
  runSearchNow: () =>
    fetchJson<SearchRunResult>("/api/search/run-now", {
      method: "POST"
    }),
  importEmmaExcel: (path: string, autoScore = true) =>
    fetchJson<EmmaExcelImportResult>("/api/import/emma-excel", {
      method: "POST",
      body: JSON.stringify({ path, auto_score: autoScore })
    }),
  uploadEmmaExcel: (file: File, autoScore = true) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("auto_score", String(autoScore));
    return fetchForm<EmmaExcelImportResult>("/api/import/emma-excel/upload", formData);
  },
  getImportRuns: () => fetchJson<ImportRun[]>("/api/import/runs"),
  getSources: () => fetchJson<Source[]>("/api/sources"),
  getConfigPreview: () => fetchJson<{ business_profile: unknown; keywords: string[] }>("/api/search/config"),
  getThrottleConfig: () => fetchJson<ThrottleConfig>("/api/search/throttle"),
  updateThrottleDefaults: (payload: Partial<ThrottleControl>) =>
    fetchJson<ThrottleConfig>("/api/search/throttle/defaults", {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  updateThrottleForSource: (sourceId: number, payload: Partial<ThrottleControl>) =>
    fetchJson<ThrottleConfig>(`/api/search/throttle/source/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  getSchedulerConfig: () => fetchJson<SchedulerConfig>("/api/scheduler"),
  getSchedulerStatus: () => fetchJson<SchedulerStatus>("/api/scheduler/status"),
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
