import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const categoryColors: Record<string, string> = {
  CODE_DEFECT: 'text-red-400 bg-red-950/40 border-red-800/50',
  FLAKY_TEST: 'text-amber-400 bg-amber-950/40 border-amber-800/50',
  DEPENDENCY: 'text-blue-400 bg-blue-950/40 border-blue-800/50',
  INFRASTRUCTURE: 'text-orange-400 bg-orange-950/40 border-orange-800/50',
  CONFIGURATION: 'text-purple-400 bg-purple-950/40 border-purple-800/50',
  UNKNOWN: 'text-slate-400 bg-slate-900/40 border-slate-700/50',
};

export const categoryChartColors: Record<string, string> = {
  CODE_DEFECT: '#f87171',
  FLAKY_TEST: '#fbbf24',
  DEPENDENCY: '#60a5fa',
  INFRASTRUCTURE: '#fb923c',
  CONFIGURATION: '#a78bfa',
  UNKNOWN: '#94a3b8',
};

export const platformLabels: Record<string, string> = {
  github_actions: 'GitHub Actions',
  jenkins: 'Jenkins',
  gitlab: 'GitLab CI/CD',
  generic: 'Generic CI/CD',
};

export function confidenceColor(score: number): string {
  if (score >= 0.8) return 'text-emerald-400';
  if (score >= 0.5) return 'text-amber-400';
  return 'text-rose-400';
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
