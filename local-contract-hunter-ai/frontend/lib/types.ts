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
  due_date?: string | null;
  description_snippet?: string | null;
  status: "Saved" | "Skipped" | "Pursue" | "Watch";
  extraction_confidence: number;
  manual_review_needed: boolean;
  score?: Score | null;
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

export type ThrottleControl = {
  max_candidate_links: number;
  page_timeout_ms: number;
  body_timeout_ms: number;
};

export type ThrottleConfig = {
  defaults: ThrottleControl;
  by_source: Record<string, ThrottleControl>;
};
