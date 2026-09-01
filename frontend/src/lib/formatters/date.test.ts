import { describe, expect, it } from 'vitest';

import { formatDate, formatDateTime } from './date';

describe('date formatters', () => {
  it('formats date-only values without timezone drift', () => {
    expect(formatDate('2026-09-01', { locale: 'en-US' })).toBe('Sep 1, 2026');
  });

  it('formats timestamps consistently', () => {
    expect(
      formatDateTime('2026-09-01T09:26:47Z', {
        locale: 'en-US',
        timeZone: 'UTC',
      }),
    ).toBe('Sep 1, 2026, 9:26 AM');
  });

  it('returns the configured fallback for missing or invalid values', () => {
    expect(formatDate(undefined)).toBe('N/A');
    expect(formatDate('2026-02-31')).toBe('N/A');
    expect(formatDateTime('not-a-date', { fallback: 'Not available' })).toBe('Not available');
  });
});
