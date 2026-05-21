export type Recommendation = "Pursue" | "Watch" | "Skip" | "Manual Review";

export type Score = {
  fit_score: number;
  skill_match: number;
  solo_fit: number;
  revenue_fit: number;
  local_fit: number;
  deadline_risk: number;
  complexity_risk: number;
  past_performance_risk: "Low" | "Medium" | "High";
  recommendation: Recommendation;
  reasoning: string;
  next_steps: string[];
};

export type Opportunity = {
  id: number;
  title: string;
  agency: string;
  source_name: string;
  source_url: string;
  opportunity_url?: string | null;
  external_id?: string | null;
  source_status?: string | null;
  last_seen_at?: string | null;
  updated_at?: string | null;
  due_date?: string | null;
  description_snippet?: string | null;
  status: "Saved" | "Skipped" | "Pursue" | "Watch";
  extraction_confidence: number;
  manual_review_needed: boolean;
  score?: Score | null;
};

export type OpportunitySearchParams = {
  page?: number;
  page_size?: number;
  q?: string;
  bpm_id?: string;
  agency?: string;
  source?: string;
  status?: string[];
  recommendation?: string[];
  source_status?: string[];
  manual_review?: boolean;
  due_from?: string;
  due_to?: string;
  created_from?: string;
  created_to?: string;
  min_confidence?: number;
  max_confidence?: number;
  min_fit_score?: number;
  max_fit_score?: number;
  min_skill_match?: number;
  min_solo_fit?: number;
  min_revenue_fit?: number;
  min_local_fit?: number;
  max_deadline_risk?: number;
  max_complexity_risk?: number;
  sort?: string;
  direction?: "asc" | "desc";
};

export type OpportunitySearchResult = {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type OpportunitySummary = {
  total: number;
  pursue: number;
  watch: number;
  skipped: number;
  manual_review: number;
  upcoming_deadlines: number;
};

export type ProposalChecklist = {
  opportunity_id: number;
  bid_recommendation: "Bid" | "Watch" | "No Bid" | "Manual Review";
  checklist_items: string[];
  risk_flags: string[];
  next_actions: string[];
  rationale: string;
};

export type DigestCandidate = {
  id: number;
  title: string;
  agency: string;
  source_name: string;
  opportunity_url?: string | null;
  due_date?: string | null;
  status: Opportunity["status"];
  fit_score: number;
  recommendation: Recommendation;
  reasoning: string;
};

export type DigestPreview = {
  generated_at: string;
  candidates: DigestCandidate[];
};

export type Source = {
  id: number;
  name: string;
  url: string;
  source_type: string;
  active: boolean;
  search_delay_seconds: number;
  notes?: string | null;
};

export type SchedulerConfig = {
  enabled: boolean;
  frequency_minutes: number;
  max_runs_per_day: number;
  jitter_seconds: number;
  last_run_at?: string | null;
  last_run_day?: string | null;
  runs_today?: number;
  last_result?: string | null;
  notes?: string | null;
};

export type SchedulerStatus = {
  enabled: boolean;
  frequency_minutes: number;
  max_runs_per_day: number;
  jitter_seconds: number;
  runs_today: number;
  last_run_at?: string | null;
  last_run_day?: string | null;
  last_result?: string | null;
  next_run_at?: string | null;
  can_run_now: boolean;
  reason: string;
};

export type SearchRunResult = {
  ok: boolean;
  skipped?: boolean;
  reason?: string;
  created?: number;
  duplicates_skipped?: number;
  sources?: number;
  runs_today?: number;
  next_run_at?: string;
};

export type EmmaExcelImportResult = {
  ok: boolean;
  import_run_id?: number | null;
  source: string;
  filename?: string | null;
  rows_seen: number;
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
  duplicates_skipped?: number;
  scored: number;
  mock_fallback_used: boolean;
};

export type ImportRun = {
  id: number;
  source_name: string;
  filename: string;
  content_type?: string | null;
  file_size_bytes: number;
  file_sha256: string;
  uploaded_at: string;
  rows_seen: number;
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
  scored: number;
  status: string;
  error_message?: string | null;
};

export type ThrottleControl = {
  max_candidate_links: number;
  page_timeout_ms: number;
  body_timeout_ms: number;
};

export type ThrottleConfig = {
  defaults: ThrottleControl;
  by_source: Record<string, ThrottleControl>;
};
