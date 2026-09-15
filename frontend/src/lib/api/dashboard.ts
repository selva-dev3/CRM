import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query';
import { z } from 'zod';

import { apiClient, captureAuthSessionGeneration, isAuthSessionGenerationCurrent, type AuthSessionGeneration } from '@/lib/api/client';
import { activitiesSummarySchema, customWidgetSchema, dashboardAiInsightsSchema, dashboardKpisSchema, funnelStageSchema, leadConversionSchema, recentDealSchema, revenueChartSchema, topPerformerSchema, type DashboardKpisDto } from '@/lib/validators/dashboard';

export type DashboardKPIs = DashboardKpisDto;
export type FunnelStageItem = z.infer<typeof funnelStageSchema>;
export type RevenueChart = z.infer<typeof revenueChartSchema>;
export type TopPerformerItem = z.infer<typeof topPerformerSchema>;
export type LeadConversionItem = z.infer<typeof leadConversionSchema>;
export type ActivitiesSummary = z.infer<typeof activitiesSummarySchema>;
export type RecentDealItem = z.infer<typeof recentDealSchema>;
export type DashboardAiInsights = z.infer<typeof dashboardAiInsightsSchema>;
export type CustomWidget = z.infer<typeof customWidgetSchema>;
export interface DashboardDateRange { startAt: string; endAt: string }
export interface MessageResponse { message: string; status: string }

export const DEFAULT_DASHBOARD_CURRENCY = 'INR';
export const DEFAULT_DASHBOARD_LOCALE = 'en-IN';
export const dashboardQueryKeys = {
  all: ['dashboard'] as const,
  kpis: (range?: DashboardDateRange) => [...dashboardQueryKeys.all, 'kpis', range] as const,
  funnel: () => [...dashboardQueryKeys.all, 'sales-funnel'] as const,
  revenue: (range: DashboardDateRange) => [...dashboardQueryKeys.all, 'revenue', range] as const,
  performers: (range?: DashboardDateRange) => [...dashboardQueryKeys.all, 'top-performers', range] as const,
  conversions: (range?: DashboardDateRange) => [...dashboardQueryKeys.all, 'lead-conversions', range] as const,
  activities: (range?: DashboardDateRange) => [...dashboardQueryKeys.all, 'activities-summary', range] as const,
  deals: (range?: DashboardDateRange) => [...dashboardQueryKeys.all, 'recent-deals', range] as const,
  insights: () => [...dashboardQueryKeys.all, 'ai-insights'] as const,
  widgets: () => [...dashboardQueryKeys.all, 'custom-widgets'] as const,
};

function withRange(path: string, range?: DashboardDateRange): string {
  if (!range) return path;
  return `${path}?${new URLSearchParams({ start_at: range.startAt, end_at: range.endAt })}`;
}
function parse<T>(schema: z.ZodType<T>, value: unknown, label: string): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new Error(`${label} response is invalid.`);
  return result.data;
}
export function parseDashboardKpis(value: unknown): DashboardKPIs {
  const result = dashboardKpisSchema.safeParse(value);
  if (result.success) return result.data;
  const metadataIssues = new Set(result.error.issues.map((issue) => issue.path[0]).filter((path) => path === 'currency' || path === 'locale'));
  const hasOtherIssue = result.error.issues.some((issue) => issue.path[0] !== 'currency' && issue.path[0] !== 'locale');
  if (metadataIssues.size && !hasOtherIssue && value && typeof value === 'object') {
    const normalized = { ...value, ...(metadataIssues.has('currency') && { currency: DEFAULT_DASHBOARD_CURRENCY }), ...(metadataIssues.has('locale') && { locale: DEFAULT_DASHBOARD_LOCALE }) };
    const retry = dashboardKpisSchema.safeParse(normalized);
    if (retry.success) return retry.data;
    throw new Error('Dashboard KPI response has invalid currency metadata.');
  }
  throw new Error('Dashboard KPI response is invalid.');
}

export async function fetchDashboardKpisApi(range?: DashboardDateRange) { return parseDashboardKpis(await apiClient.get<unknown>(withRange('/dashboard/kpis', range))); }
export async function fetchSalesFunnelApi() { return parse(z.array(funnelStageSchema), await apiClient.get<unknown>('/dashboard/sales-funnel'), 'Sales funnel'); }
export async function fetchRevenueChartApi(range: DashboardDateRange) { return parse(revenueChartSchema, await apiClient.get<unknown>(withRange('/dashboard/revenue-chart', range)), 'Revenue chart'); }
export async function fetchTopPerformersApi(range?: DashboardDateRange) { return parse(z.array(topPerformerSchema), await apiClient.get<unknown>(withRange('/dashboard/top-performers', range)), 'Top performers'); }
export async function fetchLeadConversionsApi(range?: DashboardDateRange) { return parse(z.array(leadConversionSchema), await apiClient.get<unknown>(withRange('/dashboard/lead-conversions', range)), 'Lead conversions'); }
export async function fetchActivitiesSummaryApi(range?: DashboardDateRange) { return parse(activitiesSummarySchema, await apiClient.get<unknown>(withRange('/dashboard/activities-summary', range)), 'Activity summary'); }
export async function fetchRecentDealsApi(range?: DashboardDateRange) { return parse(z.array(recentDealSchema), await apiClient.get<unknown>(withRange('/dashboard/recent-deals', range)), 'Recent deals'); }
export async function fetchDashboardAiInsightsApi() { return parse(dashboardAiInsightsSchema, await apiClient.get<unknown>('/dashboard/ai-insights'), 'AI insights'); }
export async function fetchCustomWidgetsApi() { return parse(z.array(customWidgetSchema), await apiClient.get<unknown>('/dashboard/custom-widgets'), 'Dashboard widgets'); }
export async function saveCustomWidgetsApi(widgets: CustomWidget[]): Promise<MessageResponse> { return apiClient.post('/dashboard/custom-widgets', widgets); }

type QueryOptions<T> = Omit<UseQueryOptions<T>, 'queryKey' | 'queryFn'>;
export function useDashboardKpisQuery(range?: DashboardDateRange, options?: QueryOptions<DashboardKPIs>) { return useQuery({ queryKey: dashboardQueryKeys.kpis(range), queryFn: () => fetchDashboardKpisApi(range), staleTime: 300_000, ...options }); }
export function useSalesFunnelQuery(options?: QueryOptions<FunnelStageItem[]>) { return useQuery({ queryKey: dashboardQueryKeys.funnel(), queryFn: fetchSalesFunnelApi, staleTime: 300_000, ...options }); }
export function useRevenueChartQuery(range: DashboardDateRange, options?: QueryOptions<RevenueChart>) { return useQuery({ queryKey: dashboardQueryKeys.revenue(range), queryFn: () => fetchRevenueChartApi(range), staleTime: 300_000, ...options }); }
export function useTopPerformersQuery(range?: DashboardDateRange, options?: QueryOptions<TopPerformerItem[]>) { return useQuery({ queryKey: dashboardQueryKeys.performers(range), queryFn: () => fetchTopPerformersApi(range), staleTime: 300_000, ...options }); }
export function useLeadConversionsQuery(range?: DashboardDateRange, options?: QueryOptions<LeadConversionItem[]>) { return useQuery({ queryKey: dashboardQueryKeys.conversions(range), queryFn: () => fetchLeadConversionsApi(range), staleTime: 300_000, ...options }); }
export function useActivitiesSummaryQuery(range?: DashboardDateRange, options?: QueryOptions<ActivitiesSummary>) { return useQuery({ queryKey: dashboardQueryKeys.activities(range), queryFn: () => fetchActivitiesSummaryApi(range), staleTime: 300_000, ...options }); }
export function useRecentDealsQuery(range?: DashboardDateRange, options?: QueryOptions<RecentDealItem[]>) { return useQuery({ queryKey: dashboardQueryKeys.deals(range), queryFn: () => fetchRecentDealsApi(range), staleTime: 300_000, ...options }); }
export function useDashboardAiInsightsQuery(options?: QueryOptions<DashboardAiInsights>) { return useQuery({ queryKey: dashboardQueryKeys.insights(), queryFn: fetchDashboardAiInsightsApi, staleTime: 300_000, ...options }); }
export function useCustomWidgetsQuery(options?: QueryOptions<CustomWidget[]>) { return useQuery({ queryKey: dashboardQueryKeys.widgets(), queryFn: fetchCustomWidgetsApi, staleTime: 300_000, ...options }); }
export function useSaveCustomWidgetsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveCustomWidgetsApi,
    onMutate: (): { generation: AuthSessionGeneration } => ({ generation: captureAuthSessionGeneration() }),
    onSuccess: (_response, widgets, context) => {
      if (context && isAuthSessionGenerationCurrent(context.generation)) {
        queryClient.setQueryData(dashboardQueryKeys.widgets(), widgets);
      }
    },
  });
}
