"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { SchedulerConfig, SchedulerStatus, Source, ThrottleConfig } from "@/lib/types";

type ConfigPreview = {
  business_profile: unknown;
  keywords: string[];
};

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigPreview>({ business_profile: {}, keywords: [] });
  const [scheduler, setScheduler] = useState<SchedulerConfig | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [runningNow, setRunningNow] = useState(false);
  const [customFrequency, setCustomFrequency] = useState(1440);
  const [maxRuns, setMaxRuns] = useState(2);
  const [runLogs, setRunLogs] = useState<string[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [throttleConfig, setThrottleConfig] = useState<ThrottleConfig | null>(null);
  const [defaultMaxLinks, setDefaultMaxLinks] = useState(120);
  const [defaultPageTimeout, setDefaultPageTimeout] = useState(20000);
  const [defaultBodyTimeout, setDefaultBodyTimeout] = useState(5000);

  useEffect(() => {
    api.getConfigPreview().then(setConfig).catch(() => setConfig({ business_profile: {}, keywords: [] }));
    api.getSchedulerConfig().then((data) => {
      setScheduler(data);
      setCustomFrequency(data.frequency_minutes);
      setMaxRuns(data.max_runs_per_day);
    }).catch(() => setScheduler(null));
    api.getSchedulerStatus().then(setSchedulerStatus).catch(() => setSchedulerStatus(null));
    api.getSources().then(setSources).catch(() => setSources([]));
    api.getThrottleConfig().then((cfg) => {
      setThrottleConfig(cfg);
      setDefaultMaxLinks(cfg.defaults.max_candidate_links);
      setDefaultPageTimeout(cfg.defaults.page_timeout_ms);
      setDefaultBodyTimeout(cfg.defaults.body_timeout_ms);
    }).catch(() => setThrottleConfig(null));
  }, []);

  async function toggleScheduler() {
    setSaving(true);
    try {
      const updated = await api.toggleScheduler();
      setScheduler(updated);
      const status = await api.getSchedulerStatus();
      setSchedulerStatus(status);
    } finally {
      setSaving(false);
    }
  }

  async function updateFrequency(frequency: number) {
    if (!scheduler) return;
    setSaving(true);
    try {
      const updated = await api.updateSchedulerConfig({ frequency_minutes: frequency });
      setScheduler(updated);
      setCustomFrequency(updated.frequency_minutes);
      const status = await api.getSchedulerStatus();
      setSchedulerStatus(status);
    } finally {
      setSaving(false);
    }
  }

  async function saveCustomSchedule() {
    if (!scheduler) return;
    const normalizedFrequency = Math.max(15, Math.min(10080, customFrequency));
    const normalizedMaxRuns = Math.max(1, Math.min(48, maxRuns));

    setSaving(true);
    try {
      const updated = await api.updateSchedulerConfig({
        frequency_minutes: normalizedFrequency,
        max_runs_per_day: normalizedMaxRuns,
      });
      setScheduler(updated);
      setCustomFrequency(updated.frequency_minutes);
      setMaxRuns(updated.max_runs_per_day);
      const status = await api.getSchedulerStatus();
      setSchedulerStatus(status);
    } finally {
      setSaving(false);
    }
  }

  async function runNowWithGuards() {
    setRunningNow(true);
    try {
      const result = await api.runSearchNow();
      const stamp = new Date().toLocaleString();
      const line = result.skipped
        ? `${stamp} | Skipped (${result.reason || "unknown"}) | runs today: ${result.runs_today ?? 0}`
        : `${stamp} | Ran | created: ${result.created ?? 0}, duplicates skipped: ${result.duplicates_skipped ?? 0}, runs today: ${result.runs_today ?? 0}`;
      setRunLogs((prev) => [line, ...prev].slice(0, 8));
      const status = await api.getSchedulerStatus();
      setSchedulerStatus(status);
      const cfg = await api.getSchedulerConfig();
      setScheduler(cfg);
    } catch {
      const stamp = new Date().toLocaleString();
      setRunLogs((prev) => [`${stamp} | Error running search now.`, ...prev].slice(0, 8));
    } finally {
      setRunningNow(false);
    }
  }

  async function saveThrottleDefaults() {
    setSaving(true);
    try {
      const updated = await api.updateThrottleDefaults({
        max_candidate_links: Math.max(20, Math.min(500, defaultMaxLinks)),
        page_timeout_ms: Math.max(5000, Math.min(120000, defaultPageTimeout)),
        body_timeout_ms: Math.max(2000, Math.min(60000, defaultBodyTimeout)),
      });
      setThrottleConfig(updated);
    } finally {
      setSaving(false);
    }
  }

  async function tuneSource(sourceId: number, sourceName: string, direction: "up" | "down") {
    const current = throttleConfig?.by_source?.[sourceName] || throttleConfig?.defaults;
    if (!current) return;
    const delta = direction === "up" ? 20 : -20;
    const next = Math.max(20, Math.min(500, current.max_candidate_links + delta));
    setSaving(true);
    try {
      const updated = await api.updateThrottleForSource(sourceId, { max_candidate_links: next });
      setThrottleConfig(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-ink">Settings Preview</h2>

      <div className="card">
        <h3 className="mb-2 text-base font-semibold text-ink">Automation schedule</h3>
        {!scheduler && <div className="text-sm text-slate-600">Scheduler config unavailable.</div>}
        {scheduler && (
          <div className="space-y-3">
            <div className="text-sm text-slate-700">
              Status: <span className="font-medium">{scheduler.enabled ? "Enabled" : "Disabled"}</span>
            </div>
            <div className="text-sm text-slate-700">
              Frequency: every <span className="font-medium">{scheduler.frequency_minutes}</span> minutes
            </div>
            <div className="text-sm text-slate-700">
              Max runs/day: <span className="font-medium">{scheduler.max_runs_per_day}</span>
            </div>
            {schedulerStatus && (
              <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-700">
                <div>Can run now: {schedulerStatus.can_run_now ? "Yes" : "No"}</div>
                <div>Reason: {schedulerStatus.reason}</div>
                <div>Runs today: {schedulerStatus.runs_today}</div>
                <div>Last run at: {schedulerStatus.last_run_at || "Never"}</div>
                <div>Next run at: {schedulerStatus.next_run_at || "After first run"}</div>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={toggleScheduler}
                disabled={saving}
                className="rounded-md bg-navy px-3 py-2 text-sm text-white disabled:opacity-60"
              >
                {scheduler.enabled ? "Turn Off" : "Turn On"}
              </button>
              <button
                onClick={() => updateFrequency(60)}
                disabled={saving}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                Hourly
              </button>
              <button
                onClick={() => updateFrequency(720)}
                disabled={saving}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                12 hours
              </button>
              <button
                onClick={() => updateFrequency(1440)}
                disabled={saving}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                Daily
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs text-slate-600">
                Custom frequency (minutes)
                <input
                  type="number"
                  min={15}
                  max={10080}
                  value={customFrequency}
                  onChange={(e) => setCustomFrequency(Number(e.target.value || 15))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
                />
              </label>
              <label className="text-xs text-slate-600">
                Max runs per day
                <input
                  type="number"
                  min={1}
                  max={48}
                  value={maxRuns}
                  onChange={(e) => setMaxRuns(Number(e.target.value || 1))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
                />
              </label>
            </div>
            <div>
              <button
                onClick={saveCustomSchedule}
                disabled={saving}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-60"
              >
                Save custom schedule
              </button>
            </div>
            <div>
              <button
                onClick={runNowWithGuards}
                disabled={runningNow || saving}
                className="rounded-md bg-sage px-3 py-2 text-sm text-white disabled:opacity-60"
              >
                {runningNow ? "Running..." : "Run Search Now"}
              </button>
            </div>
            {runLogs.length > 0 && (
              <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-700">
                <div className="mb-1 font-medium text-slate-800">Recent run log</div>
                {runLogs.map((line) => (
                  <div key={line}>{line}</div>
                ))}
              </div>
            )}
            <div className="text-xs text-slate-500">Use lower frequency responsibly to respect source terms and avoid heavy traffic.</div>
          </div>
        )}
      </div>

      <div className="card">
        <h3 className="mb-2 text-base font-semibold text-ink">Business profile</h3>
        <pre className="overflow-auto rounded-md bg-slate-50 p-3 text-xs text-slate-700">
          {JSON.stringify(config.business_profile, null, 2)}
        </pre>
      </div>

      <div className="card">
        <h3 className="mb-2 text-base font-semibold text-ink">Keywords</h3>
        <div className="flex flex-wrap gap-2">
          {config.keywords.map((keyword) => (
            <span key={keyword} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
              {keyword}
            </span>
          ))}
        </div>
      </div>

      <div className="card space-y-3">
        <h3 className="text-base font-semibold text-ink">Source throttle controls</h3>
        {!throttleConfig && <div className="text-sm text-slate-600">Throttle config unavailable.</div>}
        {throttleConfig && (
          <>
            <div className="grid gap-2 sm:grid-cols-3">
              <label className="text-xs text-slate-600">
                Default max candidate links
                <input
                  type="number"
                  min={20}
                  max={500}
                  value={defaultMaxLinks}
                  onChange={(e) => setDefaultMaxLinks(Number(e.target.value || 120))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
                />
              </label>
              <label className="text-xs text-slate-600">
                Default page timeout (ms)
                <input
                  type="number"
                  min={5000}
                  max={120000}
                  value={defaultPageTimeout}
                  onChange={(e) => setDefaultPageTimeout(Number(e.target.value || 20000))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
                />
              </label>
              <label className="text-xs text-slate-600">
                Default body timeout (ms)
                <input
                  type="number"
                  min={2000}
                  max={60000}
                  value={defaultBodyTimeout}
                  onChange={(e) => setDefaultBodyTimeout(Number(e.target.value || 5000))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
                />
              </label>
            </div>
            <div>
              <button
                onClick={saveThrottleDefaults}
                disabled={saving}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-60"
              >
                Save default throttle
              </button>
            </div>

            <div className="space-y-2">
              {sources.map((source) => {
                const control = throttleConfig.by_source[source.name] || throttleConfig.defaults;
                return (
                  <div key={source.id} className="rounded-md border border-slate-200 p-3">
                    <div className="text-sm font-medium text-ink">{source.name}</div>
                    <div className="mt-1 text-xs text-slate-600">
                      Max links: {control.max_candidate_links} | Page timeout: {control.page_timeout_ms}ms | Body timeout: {control.body_timeout_ms}ms
                    </div>
                    <div className="mt-2 flex gap-2">
                      <button
                        onClick={() => tuneSource(source.id, source.name, "down")}
                        disabled={saving}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                      >
                        Fewer links
                      </button>
                      <button
                        onClick={() => tuneSource(source.id, source.name, "up")}
                        disabled={saving}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                      >
                        More links
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
