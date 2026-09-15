import type { DashboardDateRange } from '@/lib/api/dashboard';

export const DASHBOARD_RANGES = [
  { value: '7d', label: 'Last 7 days', days: 7 }, { value: '30d', label: 'Last 30 days', days: 30 },
  { value: '90d', label: 'Last 90 days', days: 90 }, { value: '365d', label: 'Last 12 months', days: 365 },
] as const;
export type DashboardRangeKey = (typeof DASHBOARD_RANGES)[number]['value'];
export function isDashboardRange(value: string | null): value is DashboardRangeKey { return DASHBOARD_RANGES.some((item) => item.value === value); }
export function getDashboardDateRange(key: DashboardRangeKey, now = new Date()): DashboardDateRange {
  const days = DASHBOARD_RANGES.find((item) => item.value === key)?.days ?? 30;
  const end = new Date(now); end.setUTCHours(0, 0, 0, 0); end.setUTCDate(end.getUTCDate() + 1);
  const start = new Date(end);
  if (key === '365d') {
    start.setUTCDate(1); start.setUTCMonth(start.getUTCMonth() - 11);
  } else {
    start.setUTCDate(start.getUTCDate() - days);
  }
  return { startAt: start.toISOString(), endAt: end.toISOString() };
}
