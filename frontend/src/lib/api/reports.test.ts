import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: mocks.post,
    delete: vi.fn(),
  },
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));

import {
  exportReportCsvApi,
  exportReportPdfApi,
  getExportReportType,
  isReportType,
} from './reports';

describe('reports API contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.post.mockResolvedValue({});
  });

  it.each([
    ['performance', 'sales-performance'],
    ['velocity', 'pipeline-velocity'],
    ['winloss', 'win-loss-ratio'],
    ['attribution', 'lead-attribution'],
    ['leaderboard', 'rep-leaderboard'],
    ['forecasting', 'revenue-forecasting'],
    ['activity', 'activity-metrics'],
    ['duration', 'deal-duration'],
    ['quota', 'quota-attainment'],
  ] as const)('maps %s to canonical report type %s', (category, expected) => {
    expect(getExportReportType(category)).toBe(expected);
  });

  it.each(['unit-economics', 'custom', 'scheduled'] as const)(
    'does not export the %s management view as a normal report',
    (category) => {
      expect(getExportReportType(category)).toBeNull();
    },
  );

  it('sends canonical PDF and CSV payloads', async () => {
    await exportReportPdfApi('sales-performance');
    await exportReportCsvApi('quota-attainment');

    expect(mocks.post).toHaveBeenNthCalledWith(1, '/reports/export/pdf', {
      report_type: 'sales-performance',
    });
    expect(mocks.post).toHaveBeenNthCalledWith(2, '/reports/export/csv', {
      report_type: 'quota-attainment',
    });
  });

  it('validates report type strings at UI component boundaries', () => {
    expect(isReportType('financial-overview')).toBe(true);
    expect(isReportType('sales-performance')).toBe(true);
    expect(isReportType('performance')).toBe(false);
  });
});
