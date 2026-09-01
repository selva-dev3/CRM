import { useQuery, useMutation, UseQueryOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import {
  dashboardKpisSchema,
  type DashboardKpisDto,
} from '@/lib/validators/dashboard';

export type DashboardKPIs = DashboardKpisDto;

export const DEFAULT_DASHBOARD_CURRENCY = 'INR';
export const DEFAULT_DASHBOARD_LOCALE = 'en-IN';

export interface FunnelStageItem {
  stage: string;
  count: number;
  value: number;
}

export interface TopPerformerItem {
  name: string;
  deals_count: number;
  revenue: number;
  avatar?: string;
}

export interface LeadConversionItem {
  source: string;
  leads: number;
  converted: number;
  rate: number;
}

export interface ActivitiesSummary {
  calls_completed: number;
  emails_sent: number;
  meetings_held: number;
  tasks_completed: number;
  period_label: string;
}

export interface RecentDealItem {
  deal_id: string;
  title: string;
  amount: number;
  stage?: string;
  owner?: string;
  updated_at: string;
}

export interface AiInsightItem {
  title: string;
  description: string;
  type: 'high' | 'warning' | 'info';
  action?: string;
  deal_id?: string;
}

export interface DashboardAiInsights {
  summary: string;
  insights?: AiInsightItem[];
  risk_deals?: unknown[];
}

export interface CustomWidget {
  id: string;
  title: string;
  enabled: boolean;
}

export interface MessageResponse {
  message: string;
  status: string;
}

export function parseDashboardKpis(value: unknown): DashboardKPIs {
  const result = dashboardKpisSchema.safeParse(value);
  if (!result.success) {
    const metadataIssuePaths = new Set(
      result.error.issues
        .map((issue) => issue.path[0])
        .filter((path) => path === 'currency' || path === 'locale'),
    );
    const hasOtherIssue = result.error.issues.some(
      (issue) => issue.path[0] !== 'currency' && issue.path[0] !== 'locale',
    );

    if (metadataIssuePaths.size > 0 && !hasOtherIssue && value && typeof value === 'object') {
      const normalizedValue = {
        ...value,
        ...(metadataIssuePaths.has('currency') && {
          currency: DEFAULT_DASHBOARD_CURRENCY,
        }),
        ...(metadataIssuePaths.has('locale') && {
          locale: DEFAULT_DASHBOARD_LOCALE,
        }),
      };
      const normalizedResult = dashboardKpisSchema.safeParse(normalizedValue);
      if (normalizedResult.success) return normalizedResult.data;
      throw new Error('Dashboard KPI response has invalid currency metadata.');
    }
    throw new Error('Dashboard KPI response is invalid.');
  }
  return result.data;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchDashboardKpisApi(): Promise<DashboardKPIs> {
  return parseDashboardKpis(await apiClient.get<unknown>('/dashboard/kpis'));
}

export async function fetchSalesFunnelApi(): Promise<FunnelStageItem[]> {
  return apiClient.get<FunnelStageItem[]>('/dashboard/sales-funnel');
}

export async function fetchTopPerformersApi(): Promise<TopPerformerItem[]> {
  return apiClient.get<TopPerformerItem[]>('/dashboard/top-performers');
}

export async function fetchLeadConversionsApi(): Promise<LeadConversionItem[]> {
  return apiClient.get<LeadConversionItem[]>('/dashboard/lead-conversions');
}

export async function fetchActivitiesSummaryApi(): Promise<ActivitiesSummary> {
  return apiClient.get<ActivitiesSummary>('/dashboard/activities-summary');
}

export async function fetchRecentDealsApi(): Promise<RecentDealItem[]> {
  return apiClient.get<RecentDealItem[]>('/dashboard/recent-deals');
}

export async function fetchDashboardAiInsightsApi(): Promise<DashboardAiInsights> {
  return apiClient.get<DashboardAiInsights>('/dashboard/ai-insights');
}

export async function fetchCustomWidgetsApi(): Promise<CustomWidget[]> {
  return apiClient.get<CustomWidget[]>('/dashboard/custom-widgets');
}

export async function saveCustomWidgetsApi(widgets: CustomWidget[]): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/dashboard/custom-widgets', widgets);
}

// ---------------------------------------------------------------------------
// TanStack Query & Mutation Hooks
// ---------------------------------------------------------------------------

export function useDashboardKpisQuery(options?: Omit<UseQueryOptions<DashboardKPIs>, 'queryKey' | 'queryFn'>) {
  return useQuery<DashboardKPIs>({
    queryKey: ['dashboard', 'kpis', 'v2'],
    queryFn: fetchDashboardKpisApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useSalesFunnelQuery(options?: Omit<UseQueryOptions<FunnelStageItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<FunnelStageItem[]>({
    queryKey: ['dashboard', 'sales-funnel'],
    queryFn: fetchSalesFunnelApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useTopPerformersQuery(options?: Omit<UseQueryOptions<TopPerformerItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<TopPerformerItem[]>({
    queryKey: ['dashboard', 'top-performers'],
    queryFn: fetchTopPerformersApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useLeadConversionsQuery(options?: Omit<UseQueryOptions<LeadConversionItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<LeadConversionItem[]>({
    queryKey: ['dashboard', 'lead-conversions'],
    queryFn: fetchLeadConversionsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useActivitiesSummaryQuery(options?: Omit<UseQueryOptions<ActivitiesSummary>, 'queryKey' | 'queryFn'>) {
  return useQuery<ActivitiesSummary>({
    queryKey: ['dashboard', 'activities-summary'],
    queryFn: fetchActivitiesSummaryApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRecentDealsQuery(options?: Omit<UseQueryOptions<RecentDealItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RecentDealItem[]>({
    queryKey: ['dashboard', 'recent-deals'],
    queryFn: fetchRecentDealsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useDashboardAiInsightsQuery(options?: Omit<UseQueryOptions<DashboardAiInsights>, 'queryKey' | 'queryFn'>) {
  return useQuery<DashboardAiInsights>({
    queryKey: ['dashboard', 'ai-insights'],
    queryFn: fetchDashboardAiInsightsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useCustomWidgetsQuery(options?: Omit<UseQueryOptions<CustomWidget[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<CustomWidget[]>({
    queryKey: ['dashboard', 'custom-widgets'],
    queryFn: fetchCustomWidgetsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useSaveCustomWidgetsMutation() {
  return useMutation({
    mutationFn: saveCustomWidgetsApi,
  });
}
