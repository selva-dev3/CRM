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

  it('formats timestamps in an explicit organization timezone', () => {
    expect(
      formatDateTime('2026-09-01T09:26:47Z', {
        locale: 'en-US',
        timeZone: 'Asia/Kolkata',
      }),
    ).toBe('Sep 1, 2026, 2:56 PM');

    expect(
      formatDate('2026-08-31T20:00:00Z', {
        locale: 'en-US',
        timeZone: 'Asia/Kolkata',
      }),
    ).toBe('Sep 1, 2026');
  });

  it('returns the configured fallback for missing or invalid values', () => {
    expect(formatDate(undefined)).toBe('N/A');
    expect(formatDate('2026-02-31')).toBe('N/A');
    expect(formatDateTime('not-a-date', { fallback: 'Not available' })).toBe('Not available');
  });

  it('falls back to UTC when an organization timezone is invalid', () => {
    expect(
      formatDateTime('2026-09-01T09:26:47Z', {
        locale: 'en-US',
        timeZone: 'Invalid/Timezone',
      }),
    ).toBe('Sep 1, 2026, 9:26 AM');
  });
});
