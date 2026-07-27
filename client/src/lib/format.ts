import type { AnalysisStatus, BugSeverity, ProjectStatus } from '../types';

/** Tailwind class sets keyed by domain enum, so badges look identical everywhere. */
export const SEVERITY_STYLES: Record<BugSeverity, string> = {
  LOW: 'bg-slate-500/10 text-slate-300 border-slate-500/30',
  MEDIUM: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  HIGH: 'bg-orange-500/10 text-orange-300 border-orange-500/30',
  CRITICAL: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
};

export const CONFIDENCE_STYLES: Record<string, string> = {
  HIGH: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  MEDIUM: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  LOW: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
};

export const ANALYSIS_STATUS_STYLES: Record<AnalysisStatus, string> = {
  pending: 'bg-slate-500/10 text-slate-300 border-slate-500/30',
  processing: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30',
  completed: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  failed: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
};

/** A project is still moving through the indexing pipeline. */
export function isIndexing(status: ProjectStatus): boolean {
  return status !== 'READY' && status !== 'FAILED';
}

export function formatDate(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelative(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return date.toLocaleDateString();
}

export function formatDuration(ms?: number): string {
  if (ms === undefined || ms === null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function fileName(filePath?: string): string {
  if (!filePath) return '—';
  return filePath.split('/').pop() || filePath;
}
