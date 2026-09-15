import { describe, expect, it } from 'vitest';

import { formatDashboardDealDate } from './dashboard-deals-table';

describe('formatDashboardDealDate', () => {
  it('treats date-only API values as local calendar dates', () => {
    const expected = new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(new Date(2026, 8, 15));

    expect(formatDashboardDealDate('2026-09-15')).toBe(expected);
  });

  it('preserves non-date fallback text without throwing', () => {
    expect(formatDashboardDealDate('Today')).toBe('Today');
    expect(formatDashboardDealDate('')).toBe('Recently updated');
  });
});
