import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchDashboardKpisApi, parseDashboardKpis } from './dashboard';

const validKpis = {
  total_leads: 7,
  deals_won_amount: 5000,
  pipeline_revenue: 1200,
  win_rate_percentage: 50,
  won_deals_count: 1,
  closed_deals_count: 2,
  ai_lead_score_avg: 72,
  scored_leads_count: 4,
  currency: 'INR',
  locale: 'en-IN',
  recent_activity: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('dashboard KPI response validation', () => {
  it('accepts a complete KPI response with currency metadata', () => {
    expect(parseDashboardKpis(validKpis)).toEqual(validKpis);
  });

  it('rejects a legacy response that omits pipeline revenue', () => {
    const legacyKpis: Partial<typeof validKpis> = { ...validKpis };
    delete legacyKpis.pipeline_revenue;

    expect(() => parseDashboardKpis(legacyKpis)).toThrow('Dashboard KPI response is invalid.');
  });

  it('rejects an unknown three-letter currency code', () => {
    expect(() => parseDashboardKpis({ ...validKpis, currency: 'XYZ' })).toThrow(
      'Dashboard KPI response has invalid currency metadata.',
    );
  });

  it('turns an invalid API payload into a rejected query result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({ total_leads: 7 }),
    }));

    await expect(fetchDashboardKpisApi()).rejects.toThrow('Dashboard KPI response is invalid.');
  });
});
