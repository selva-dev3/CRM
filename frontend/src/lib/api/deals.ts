import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { QueryClient, useQueryClient } from '@tanstack/react-query';
import {
  fetchEntityCustomFieldsApi,
  useEntityCustomFieldsQuery,
  type CustomFieldDefinition,
  type CustomFieldValue,
} from '@/lib/api/custom-fields';
import type {
  ActionResponse,
  DealCommissionResponse,
  DealPredictionResponse,
  DealProductItem,
  DealStageItem,
  DealWinLossAnalytics,
  RelatedRecord,
} from '@/lib/types';

export interface DealItem {
  id: string;
  title: string;
  amount: number;
  stage: string;
  probability?: number;
  expected_close_date?: string;
  company_id?: string;
  contact_id?: string;
  assigned_to?: string;
  organization_id?: string;
  created_at?: string;
  custom_fields?: Record<string, CustomFieldValue>;
  project_id?: string;
}

export type DealCustomFieldDefinition = CustomFieldDefinition;

export interface DealCreatePayload {
  title: string;
  amount: number;
  stage: string;
  probability?: number;
  company_id?: string;
  contact_id?: string;
  assigned_to?: string;
  custom_fields?: Record<string, CustomFieldValue>;
  project_id?: string;
}

export interface DealUpdatePayload {
  title?: string;
  amount?: number;
  stage?: string;
  probability?: number;
  company_id?: string;
  contact_id?: string;
  assigned_to?: string;
  custom_fields?: Record<string, CustomFieldValue>;
  project_id?: string;
}

// API Functions
export async function fetchDealsApi(page = 1, limit = 20, stage?: string, search?: string): Promise<DealItem[]> {
  const query = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (stage) query.append('stage', stage);
  if (search) query.append('search', search);
  return apiClient.get<DealItem[]>(`/deals?${query.toString()}`);
}

export async function createDealApi(payload: DealCreatePayload): Promise<DealItem> {
  return apiClient.post<DealItem>('/deals', payload);
}

export async function fetchDealCustomFieldsApi(): Promise<DealCustomFieldDefinition[]> {
  return fetchEntityCustomFieldsApi('Deal');
}

export async function getDealStagesApi(): Promise<DealStageItem[]> {
  try {
    return await apiClient.get<DealStageItem[]>('/deals/stages');
  } catch {
    return [
      { id: 'stg-1', name: 'Prospecting', probability: 10 },
      { id: 'stg-2', name: 'Qualification', probability: 30 },
      { id: 'stg-3', name: 'Proposal', probability: 60 },
      { id: 'stg-4', name: 'Negotiation', probability: 80 },
      { id: 'stg-5', name: 'Closed Won', probability: 100 },
      { id: 'stg-6', name: 'Closed Lost', probability: 0 },
    ];
  }
}

export async function createDealStageApi(payload: { name: string; probability: number }): Promise<DealStageItem> {
  return apiClient.post<DealStageItem>(`/deals/stages?name=${encodeURIComponent(payload.name)}&probability=${payload.probability}`);
}

export async function getKanbanBoardApi(): Promise<Record<string, DealItem[]>> {
  try {
    return await apiClient.get<Record<string, DealItem[]>>('/deals/kanban');
  } catch {
    return {};
  }
}

export async function getWinLossAnalyticsApi(): Promise<DealWinLossAnalytics> {
  try {
    return await apiClient.get('/deals/win-loss-analytics');
  } catch {
    return { win_rate: 0.0, won_count: 0, lost_count: 0, top_loss_reasons: [] };
  }
}

export async function exportDealsCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/deals/export/csv');
}

export async function importDealsCsvApi(): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/deals/import/csv');
}

export async function bulkDeleteDealsApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post<{ affected_count: number; message: string }>('/deals/bulk-delete', { ids });
}

export async function bulkUpdateDealStageApi(payload: { ids: string[]; stage: string }): Promise<ActionResponse> {
  return apiClient.post<ActionResponse>(`/deals/bulk-update-stage?stage=${encodeURIComponent(payload.stage)}`, { ids: payload.ids });
}

export async function getDealApi(id: string): Promise<DealItem> {
  return apiClient.get<DealItem>(`/deals/${id}`);
}

export async function updateDealApi(payload: { id: string; data: DealUpdatePayload }): Promise<DealItem> {
  return apiClient.put<DealItem>(`/deals/${payload.id}`, payload.data);
}

export async function deleteDealApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/deals/${id}`);
}

export async function updateDealStageApi(payload: { id: string; stage: string }): Promise<ActionResponse> {
  return apiClient.post<ActionResponse>(`/deals/${payload.id}/stage?stage=${encodeURIComponent(payload.stage)}`);
}

export interface DealWonResponse extends ActionResponse {
  deal_id: string;
  stage: string;
  quote_id: string;
  quote_status: string;
}

export async function markDealWonApi(payload: { id: string; final_amount?: number }): Promise<DealWonResponse> {
  const query = payload.final_amount ? `?final_amount=${payload.final_amount}` : '';
  return apiClient.post<DealWonResponse>(`/deals/${payload.id}/win${query}`);
}

export async function markDealLostApi(payload: { id: string; reason: string }): Promise<ActionResponse> {
  return apiClient.post<ActionResponse>(`/deals/${payload.id}/lose?reason=${encodeURIComponent(payload.reason)}`);
}

export async function assignDealApi(payload: { id: string; user_id: string }): Promise<ActionResponse> {
  return apiClient.post<ActionResponse>(`/deals/${payload.id}/assign?user_id=${encodeURIComponent(payload.user_id)}`);
}

export async function getDealProductsApi(id: string): Promise<DealProductItem[]> {
  try {
    return await apiClient.get<DealProductItem[]>(`/deals/${id}/products`);
  } catch {
    return [];
  }
}

export async function addDealProductApi(payload: { id: string; product_id: string; quantity?: number; unit_price?: number; custom_name?: string }): Promise<ActionResponse> {
  const query = new URLSearchParams({
    product_id: payload.product_id,
    quantity: String(payload.quantity || 1),
  });
  if (payload.unit_price !== undefined) query.append('unit_price', String(payload.unit_price));
  if (payload.custom_name) query.append('custom_name', payload.custom_name);
  return apiClient.post<ActionResponse>(`/deals/${payload.id}/products?${query.toString()}`);
}

export async function removeDealProductApi(payload: { id: string; product_id: string }): Promise<ActionResponse> {
  return apiClient.delete<ActionResponse>(`/deals/${payload.id}/products/${payload.product_id}`);
}

export async function getDealTimelineApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/deals/${id}/timeline`);
  } catch {
    return [];
  }
}

export async function getDealNotesApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/deals/${id}/notes`);
  } catch {
    return [];
  }
}

export async function addDealNoteApi(payload: { id: string; content: string }): Promise<RelatedRecord> {
  return apiClient.post<RelatedRecord>(`/deals/${payload.id}/notes?content=${encodeURIComponent(payload.content)}`, {
    content: payload.content,
  });
}

export async function getDealQuotesApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/deals/${id}/quotes`);
  } catch {
    return [];
  }
}

export async function predictDealWinRateApi(id: string): Promise<DealPredictionResponse> {
  return apiClient.post<DealPredictionResponse>(`/deals/${id}/predict-win-rate`);
}

export async function cloneDealApi(payload: { id: string; new_title: string }): Promise<DealItem> {
  return apiClient.post<DealItem>(`/deals/${payload.id}/clone?new_title=${encodeURIComponent(payload.new_title)}`);
}

export async function getDealCommissionApi(id: string): Promise<DealCommissionResponse | null> {
  try {
    return await apiClient.get<DealCommissionResponse>(`/deals/${id}/commission`);
  } catch {
    return null;
  }
}

// TanStack Query & Mutation Hooks
function invalidateDealReports(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: ['deals'] });
  queryClient.invalidateQueries({ queryKey: ['kanban-board'] });
  queryClient.invalidateQueries({ queryKey: ['win-loss-analytics'] });
  queryClient.invalidateQueries({ queryKey: ['reports'] });
}

export function useDealsQuery(page = 1, limit = 20, stage?: string, search?: string) {
  return useQuery({
    queryKey: ['deals', page, limit, stage, search],
    queryFn: () => fetchDealsApi(page, limit, stage, search),
    placeholderData: (previousData) => previousData,
  });
}

export function useDealQuery(id: string) {
  return useQuery({
    queryKey: ['deal', id],
    queryFn: () => getDealApi(id),
    enabled: !!id,
  });
}

export function useDealCustomFieldsQuery(enabled = true) {
  return useEntityCustomFieldsQuery('Deal', enabled);
}

export function useDealStagesQuery() {
  return useQuery({
    queryKey: ['deal-stages'],
    queryFn: getDealStagesApi,
  });
}

export function useKanbanBoardQuery() {
  return useQuery({
    queryKey: ['kanban-board'],
    queryFn: getKanbanBoardApi,
  });
}

export function useWinLossAnalyticsQuery() {
  return useQuery({
    queryKey: ['win-loss-analytics'],
    queryFn: getWinLossAnalyticsApi,
  });
}

export function useCreateDealMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDealApi,
    onSuccess: () => invalidateDealReports(queryClient),
  });
}

export function useUpdateDealMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateDealApi,
    onSuccess: (_, variables) => {
      invalidateDealReports(queryClient);
      queryClient.invalidateQueries({ queryKey: ['deal', variables.id] });
    },
  });
}

export function useDeleteDealMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDealApi,
    onSuccess: () => invalidateDealReports(queryClient),
  });
}

export function useUpdateDealStageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateDealStageApi,
    onSuccess: (_, variables) => {
      invalidateDealReports(queryClient);
      queryClient.invalidateQueries({ queryKey: ['deal', variables.id] });
    },
  });
}

export function useMarkDealWonMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markDealWonApi,
    onSuccess: (_, variables) => {
      invalidateDealReports(queryClient);
      queryClient.invalidateQueries({ queryKey: ['deal', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
    },
  });
}

export function useMarkDealLostMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markDealLostApi,
    onSuccess: (_, variables) => {
      invalidateDealReports(queryClient);
      queryClient.invalidateQueries({ queryKey: ['deal', variables.id] });
    },
  });
}

export function useBulkDeleteDealsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkDeleteDealsApi,
    onSuccess: () => invalidateDealReports(queryClient),
  });
}

export function useBulkUpdateDealStageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkUpdateDealStageApi,
    onSuccess: () => {
      invalidateDealReports(queryClient);
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
    },
  });
}

export function useImportDealsCsvMutation() {
  return useMutation({
    mutationFn: importDealsCsvApi,
  });
}
