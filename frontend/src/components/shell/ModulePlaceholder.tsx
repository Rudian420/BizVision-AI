'use client';

import { useEffect, useState } from 'react';

import type { ModuleMeta } from '@/lib/modules';
import { apiClient } from '@/lib/api-client';

/**
 * Wave-1 placeholder for a module page.
 *
 * Renders the module's accent header + a "health" badge that pings
 * the backend's `/health` route to confirm the workspace is live.
 * The real module UI (FE-011..015) replaces this in a later session.
 */
type HealthState = 'idle' | 'loading' | 'ok' | 'error';

export function ModulePlaceholder({ module }: { module: ModuleMeta }) {
  const [health, setHealth] = useState<HealthState>('idle');
  const [healthDetail, setHealthDetail] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    setHealth('loading');
    apiClient
      .get<unknown>('/health', { baseURL: apiClient.defaults.baseURL?.replace(/\/api\/v1\/?$/, '') })
      .then((res) => {
        if (cancelled) return;
        setHealth('ok');
        setHealthDetail(JSON.stringify(res.data));
      })
      .catch(() => {
        if (cancelled) return;
        setHealth('error');
        setHealthDetail('backend unreachable');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <header className="mb-8 border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: module.accent }}>
            {module.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            {module.id} module
          </span>
        </div>
        <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">{module.label}</h2>
        <p className="mt-2 font-ui text-sm text-text-secondary">{module.tagline}</p>
      </header>

      <section aria-label="Module placeholder" className="rounded-2xl border border-white/10 bg-white/[0.02] p-8">
        <p className="font-ui text-sm text-text-secondary">{module.blurb}</p>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <Stat label={module.statLabel} value={module.stat} accent={module.accent} />
          <Stat label="API status" value={statusLabel(health)} accent={statusAccent(health, module.accent)} />
          <Stat label="UI wave" value="1 (placeholder)" accent="#FFFFFF" />
        </div>

        <p className="mt-6 font-ui text-xs text-text-secondary">
          Full interface (FE-{moduleNumber(module.id)}) ships in a later session — the AI module is already live via
          the backend.
        </p>

        {health === 'error' && (
          <p className="mt-4 rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-xs text-coral">
            Backend unreachable. Start it with <code className="font-data">docker compose up backend</code>.
          </p>
        )}

        {health === 'ok' && healthDetail && (
          <pre className="mt-4 overflow-x-auto rounded-md border border-emerald/30 bg-emerald/5 px-3 py-2 font-data text-[11px] text-emerald">
            {healthDetail}
          </pre>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-void/40 p-4">
      <div className="font-data text-lg font-semibold" style={{ color: accent }}>
        {value}
      </div>
      <div className="mt-1 font-ui text-[10px] uppercase tracking-widest text-text-secondary">{label}</div>
    </div>
  );
}

function statusLabel(state: HealthState): string {
  switch (state) {
    case 'loading':
      return 'checking…';
    case 'ok':
      return 'live';
    case 'error':
      return 'down';
    case 'idle':
    default:
      return 'idle';
  }
}

function statusAccent(state: HealthState, fallback: string): string {
  if (state === 'ok') return '#10F07C';
  if (state === 'error') return '#FF3B6B';
  return fallback;
}

function moduleNumber(id: ModuleMeta['id']): string {
  switch (id) {
    case 'recruitment':
      return '011';
    case 'pricing':
      return '012';
    case 'forecasting':
      return '013';
    case 'sustainability':
      return '014';
    case 'chatbot':
      return '015';
  }
}
