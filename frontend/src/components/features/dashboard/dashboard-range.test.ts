import { describe, expect, it } from 'vitest';
import { getDashboardDateRange, isDashboardRange } from './dashboard-range';

describe('dashboard date ranges', () => {
  it('creates a stable UTC range', () => {
    expect(getDashboardDateRange('30d', new Date('2026-09-15T10:00:00.000Z'))).toEqual({ startAt: '2026-08-17T00:00:00.000Z', endAt: '2026-09-16T00:00:00.000Z' });
  });
  it('uses exactly twelve calendar-month buckets for the annual range', () => {
    expect(getDashboardDateRange('365d', new Date('2026-09-15T10:00:00.000Z'))).toEqual({ startAt: '2025-10-01T00:00:00.000Z', endAt: '2026-09-16T00:00:00.000Z' });
  });
  it('rejects unsupported URL values', () => { expect(isDashboardRange('30d')).toBe(true); expect(isDashboardRange('all')).toBe(false); expect(isDashboardRange(null)).toBe(false); });
});
