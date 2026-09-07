import { afterEach, describe, expect, it, vi } from 'vitest';

const validKpis = {
  total_leads: 7,
  deals_won_amount: 5000,
  pipeline_revenue: 1200,
  win_rate_percentage: 50,
  won_deals_count: 1,
  closed_deals_count: 2,
  ai_lead_score_avg: 72,
  scored_leads_count: 4,
  quote_count: 3,
  quote_value: 9000,
  quote_conversion_percentage: 50,
  invoice_count: 2,
  invoice_total: 6000,
  paid_amount: 4000,
  outstanding_amount: 2000,
  pending_payment_count: 1,
  partially_paid_invoice_count: 0,
  paid_invoice_count: 1,
  revenue: 4000,
  collection_rate_percentage: 66.67,
  currency: 'INR',
  locale: 'en-IN',
  recent_activity: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('dashboard KPI validator runtime compatibility', () => {
  it('loads when Intl.supportedValuesOf is unavailable', async () => {
    vi.stubGlobal('Intl', { NumberFormat: Intl.NumberFormat });
    vi.resetModules();

    const { dashboardKpisSchema } = await import('./dashboard');

    expect(dashboardKpisSchema.safeParse(validKpis).success).toBe(true);
  });

  it('loads when Intl.supportedValuesOf throws', async () => {
    vi.stubGlobal('Intl', {
      NumberFormat: Intl.NumberFormat,
      supportedValuesOf: () => {
        throw new Error('unsupported runtime');
      },
    });
    vi.resetModules();

    const { dashboardKpisSchema } = await import('./dashboard');

    expect(dashboardKpisSchema.safeParse(validKpis).success).toBe(true);
  });
});
