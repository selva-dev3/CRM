import { z } from 'zod';

function getSupportedCurrencyCodes(): Set<string> | null {
  try {
    if (typeof Intl === 'undefined' || typeof Intl.supportedValuesOf !== 'function') return null;
    return new Set(Intl.supportedValuesOf('currency'));
  } catch {
    return null;
  }
}

const supportedCurrencyCodes = getSupportedCurrencyCodes();

const currencyCodeSchema = z.string()
  .regex(/^[A-Z]{3}$/)
  .refine((currency) => supportedCurrencyCodes === null || supportedCurrencyCodes.has(currency));

export const dashboardKpisSchema = z.object({
  total_leads: z.number().finite().nonnegative(),
  deals_won_amount: z.number().finite().nonnegative(),
  pipeline_revenue: z.number().finite().nonnegative(),
  win_rate_percentage: z.number().finite().min(0).max(100),
  won_deals_count: z.number().finite().nonnegative(),
  closed_deals_count: z.number().finite().nonnegative(),
  ai_lead_score_avg: z.number().finite().min(0).max(100),
  scored_leads_count: z.number().finite().nonnegative(),
  quote_count: z.number().finite().nonnegative(),
  quote_value: z.number().finite().nonnegative(),
  quote_conversion_percentage: z.number().finite().min(0).max(100),
  invoice_count: z.number().finite().nonnegative(),
  invoice_total: z.number().finite().nonnegative(),
  paid_amount: z.number().finite().nonnegative(),
  outstanding_amount: z.number().finite().nonnegative(),
  pending_payment_count: z.number().finite().nonnegative(),
  partially_paid_invoice_count: z.number().finite().nonnegative(),
  paid_invoice_count: z.number().finite().nonnegative(),
  revenue: z.number().finite().nonnegative(),
  collection_rate_percentage: z.number().finite().min(0).max(100),
  currency: currencyCodeSchema,
  locale: z.string().min(2).max(20),
  recent_activity: z.array(z.object({
    action: z.string(),
    title: z.string(),
    user: z.string(),
    timestamp: z.string(),
  })),
  period: z.object({ start_at: z.string().datetime(), end_at: z.string().datetime() }).nullable().optional(),
  comparisons: z.object({
    total_leads: z.object({ previous_value: z.number().nonnegative(), change_percentage: z.number().nullable() }),
    deals_won_amount: z.object({ previous_value: z.number().nonnegative(), change_percentage: z.number().nullable() }),
    won_deals_count: z.object({ previous_value: z.number().nonnegative(), change_percentage: z.number().nullable() }),
    win_rate_percentage: z.object({ previous_value: z.number().nonnegative(), change_percentage: z.number().nullable() }),
    quote_value: z.object({ previous_value: z.number().nonnegative(), change_percentage: z.number().nullable() }),
    revenue: z.object({ previous_value: z.number().nonnegative(), change_percentage: z.number().nullable() }),
  }).nullable().optional(),
}).superRefine((value, context) => {
  try {
    new Intl.NumberFormat(value.locale, {
      style: 'currency',
      currency: value.currency,
    }).format(0);
  } catch {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['locale'],
      message: 'Invalid currency locale.',
    });
  }
});

export type DashboardKpisDto = z.infer<typeof dashboardKpisSchema>;

export const funnelStageSchema = z.object({ stage: z.string(), count: z.number().int().nonnegative(), value: z.number().finite().nonnegative() });
export const revenueChartSchema = z.object({ months: z.array(z.string()), actual: z.array(z.number().finite().nonnegative()), target: z.array(z.number().finite().nonnegative()) }).refine((value) => value.months.length === value.actual.length, { message: 'Revenue chart labels and values must have matching lengths.' });
export const topPerformerSchema = z.object({ name: z.string(), deals_count: z.number().int().nonnegative(), revenue: z.number().finite().nonnegative(), avatar: z.string().optional() });
export const leadConversionSchema = z.object({ source: z.string(), leads: z.number().int().nonnegative(), converted: z.number().int().nonnegative(), rate: z.number().finite().min(0).max(100) });
export const activitiesSummarySchema = z.object({ calls_completed: z.number().int().nonnegative(), emails_sent: z.number().int().nonnegative(), meetings_held: z.number().int().nonnegative(), tasks_completed: z.number().int().nonnegative(), period_label: z.string() });
export const recentDealSchema = z.object({ deal_id: z.string(), title: z.string(), amount: z.number().finite().nonnegative(), stage: z.string().optional(), owner: z.string().optional(), updated_at: z.string() });
export const dashboardAiInsightsSchema = z.object({
  summary: z.string(),
  insights: z.array(z.object({ title: z.string(), description: z.string(), type: z.enum(['high', 'warning', 'info']), action: z.string().nullable().optional(), deal_id: z.string().nullable().optional() })).optional(),
  risk_deals: z.array(z.object({ id: z.string(), title: z.string(), amount: z.number().finite().nonnegative().nullable().optional(), stage: z.string(), probability: z.number().finite().min(0).max(100).nullable().optional(), updated_at: z.string() })).optional(),
  run_id: z.string().nullable().optional(),
});
export const customWidgetSchema = z.object({ id: z.string(), title: z.string(), enabled: z.boolean() });
