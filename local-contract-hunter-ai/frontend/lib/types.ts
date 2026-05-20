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
  notes?: string | null;
};
