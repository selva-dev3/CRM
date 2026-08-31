import { useQuery, useMutation, UseQueryOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface DashboardKPIs {
  total_leads: number;
  deals_won_amount: number;
  pipeline_revenue: number;
  win_rate_percentage: number;
  won_deals_count: number;
  closed_deals_count: number;
  ai_lead_score_avg: number;
  scored_leads_count: number;
  recent_activity?: Array<{ action: string; title: string; user: string; timestamp: string }>;
}

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

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchDashboardKpisApi(): Promise<DashboardKPIs> {
  return apiClient.get<DashboardKPIs>('/dashboard/kpis');
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
    queryKey: ['dashboard', 'kpis'],
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
