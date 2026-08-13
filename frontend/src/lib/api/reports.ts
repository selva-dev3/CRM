import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ReportData {
  report_type: string;
  metrics: Record<string, any>;
  generated_at: string;
}

export interface CustomReportItem {
  id: string;
  name: string;
  metrics_included?: string[];
  created_at: string;
}

export interface ScheduledReportItem {
  id: string;
  report_type: string;
  email: string;
  frequency: string;
  next_run: string;
}

export interface MessageResponse {
  message: string;
  status: string;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchSalesPerformanceReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/sales-performance');
}

export async function fetchPipelineVelocityReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/pipeline-velocity');
}

export async function fetchWinLossReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/win-loss-ratio');
}

export async function fetchLeadAttributionReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/lead-attribution');
}

export async function fetchRepLeaderboardReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/rep-leaderboard');
}

export async function fetchRevenueForecastingReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/revenue-forecasting');
}

export async function fetchActivityMetricsReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/activity-metrics');
}

export async function fetchDealDurationReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/deal-duration');
}

export async function fetchCacReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/customer-acquisition-cost');
}

export async function fetchLtvReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/customer-lifetime-value');
}

export async function fetchChurnAnalysisReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/churn-analysis');
}

export async function fetchQuotaAttainmentReportApi(): Promise<ReportData> {
  return apiClient.get<ReportData>('/reports/quota-attainment');
}

export async function fetchCustomReportsApi(): Promise<CustomReportItem[]> {
  return apiClient.get<CustomReportItem[]>('/reports/custom-reports');
}

export async function createCustomReportApi(name: string, filters?: string): Promise<MessageResponse> {
  const query = new URLSearchParams({ name });
  if (filters) query.append('filters', filters);
  return apiClient.post<MessageResponse>(`/reports/custom-reports?${query.toString()}`);
}

export async function runCustomReportApi(reportId: string): Promise<ReportData> {
  return apiClient.get<ReportData>(`/reports/custom-reports/${reportId}`);
}

export async function deleteCustomReportApi(reportId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/reports/custom-reports/${reportId}`);
}

export async function exportReportPdfApi(report_type: string = 'sales-performance'): Promise<{ pdf_url: string }> {
  return apiClient.post<{ pdf_url: string }>(`/reports/export/pdf?report_type=${encodeURIComponent(report_type)}`);
}

export async function exportReportCsvApi(report_type: string = 'sales-performance'): Promise<{ csv_url: string }> {
  return apiClient.post<{ csv_url: string }>(`/reports/export/csv?report_type=${encodeURIComponent(report_type)}`);
}

export async function scheduleReportEmailApi(report_type: string, email: string, frequency: string = 'Weekly'): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/reports/schedule?report_type=${encodeURIComponent(report_type)}&email=${encodeURIComponent(email)}&frequency=${encodeURIComponent(frequency)}`);
}

export async function fetchScheduledReportsApi(): Promise<ScheduledReportItem[]> {
  return apiClient.get<ScheduledReportItem[]>('/reports/scheduled');
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useSalesPerformanceReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'sales-performance'],
    queryFn: fetchSalesPerformanceReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function usePipelineVelocityReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'pipeline-velocity'],
    queryFn: fetchPipelineVelocityReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useWinLossReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'win-loss-ratio'],
    queryFn: fetchWinLossReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useLeadAttributionReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'lead-attribution'],
    queryFn: fetchLeadAttributionReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRepLeaderboardReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'rep-leaderboard'],
    queryFn: fetchRepLeaderboardReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRevenueForecastingReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'revenue-forecasting'],
    queryFn: fetchRevenueForecastingReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useActivityMetricsReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'activity-metrics'],
    queryFn: fetchActivityMetricsReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useDealDurationReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'deal-duration'],
    queryFn: fetchDealDurationReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useCacReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'customer-acquisition-cost'],
    queryFn: fetchCacReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useLtvReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'customer-lifetime-value'],
    queryFn: fetchLtvReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useChurnAnalysisReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'churn-analysis'],
    queryFn: fetchChurnAnalysisReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useQuotaAttainmentReportQuery(options?: Omit<UseQueryOptions<ReportData>, 'queryKey' | 'queryFn'>) {
  return useQuery<ReportData>({
    queryKey: ['reports', 'quota-attainment'],
    queryFn: fetchQuotaAttainmentReportApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useCustomReportsQuery(options?: Omit<UseQueryOptions<CustomReportItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<CustomReportItem[]>({
    queryKey: ['reports', 'custom-reports'],
    queryFn: fetchCustomReportsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useScheduledReportsQuery(options?: Omit<UseQueryOptions<ScheduledReportItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<ScheduledReportItem[]>({
    queryKey: ['reports', 'scheduled'],
    queryFn: fetchScheduledReportsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useCreateCustomReportMutation(options?: UseMutationOptions<MessageResponse, Error, { name: string; filters?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { name: string; filters?: string }>({
    mutationFn: ({ name, filters }) => createCustomReportApi(name, filters),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports', 'custom-reports'] });
    },
    ...options,
  });
}

export function useDeleteCustomReportMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteCustomReportApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports', 'custom-reports'] });
    },
    ...options,
  });
}

export function useExportReportPdfMutation(options?: UseMutationOptions<{ pdf_url: string }, Error, string | undefined>) {
  return useMutation<{ pdf_url: string }, Error, string | undefined>({
    mutationFn: (reportType) => exportReportPdfApi(reportType),
    ...options,
  });
}

export function useExportReportCsvMutation(options?: UseMutationOptions<{ csv_url: string }, Error, string | undefined>) {
  return useMutation<{ csv_url: string }, Error, string | undefined>({
    mutationFn: (reportType) => exportReportCsvApi(reportType),
    ...options,
  });
}

export function useScheduleReportEmailMutation(options?: UseMutationOptions<MessageResponse, Error, { report_type: string; email: string; frequency?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { report_type: string; email: string; frequency?: string }>({
    mutationFn: ({ report_type, email, frequency }) => scheduleReportEmailApi(report_type, email, frequency),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports', 'scheduled'] });
    },
    ...options,
  });
}
