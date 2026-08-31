import { z } from 'zod';

const supportedCurrencyCodes = new Set(Intl.supportedValuesOf('currency'));

const currencyCodeSchema = z.string()
  .regex(/^[A-Z]{3}$/)
  .refine((currency) => supportedCurrencyCodes.has(currency));

export const dashboardKpisSchema = z.object({
  total_leads: z.number().finite().nonnegative(),
  deals_won_amount: z.number().finite().nonnegative(),
  pipeline_revenue: z.number().finite().nonnegative(),
  win_rate_percentage: z.number().finite().min(0).max(100),
  won_deals_count: z.number().finite().nonnegative(),
  closed_deals_count: z.number().finite().nonnegative(),
  ai_lead_score_avg: z.number().finite().min(0).max(100),
  scored_leads_count: z.number().finite().nonnegative(),
  currency: currencyCodeSchema,
  locale: z.string().min(2).max(20),
  recent_activity: z.array(z.object({
    action: z.string(),
    title: z.string(),
    user: z.string(),
    timestamp: z.string(),
  })),
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
