"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { SchedulerConfig } from "@/lib/types";

type ConfigPreview = {
  business_profile: unknown;
  keywords: string[];
};

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigPreview>({ business_profile: {}, keywords: [] });
  const [scheduler, setScheduler] = useState<SchedulerConfig | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getConfigPreview().then(setConfig).catch(() => setConfig({ business_profile: {}, keywords: [] }));
    api.getSchedulerConfig().then(setScheduler).catch(() => setScheduler(null));
  }, []);

  async function toggleScheduler() {
    setSaving(true);
    try {
      const updated = await api.toggleScheduler();
      setScheduler(updated);
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
    </div>
  );
}
