import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';
import type { CustomFieldValue } from '@/lib/api/custom-fields';
import {
  deleteCallApi,
  updateCallApi,
  type CallLogBasePayload,
  type CallLogItem,
  type CallLogUpdatePayload,
} from '@/lib/api/calls';

export interface Lead {
  id: string;
  title: string;
  company: string;
  contact_name: string;
  email: string;
  phone?: string;
  website?: string;
  industry?: string;
  company_size?: string;
  country?: string;
  state?: string;
  city?: string;
  address?: string;
  postal_code?: string;
  status: string;
  source: string;
  score?: number;
  assigned_to?: string | null;
  is_archived?: boolean;
  organization_id?: string;
  created_at?: string;
  updated_at?: string;
  qualification_reason?: string | null;
  qualified_at?: string | null;
  qualified_by?: string | null;
  disqualified_at?: string | null;
  disqualified_by?: string | null;
  converted_at?: string | null;
  converted_by?: string | null;
  converted_company_id?: string | null;
  converted_contact_id?: string | null;
  converted_deal_id?: string | null;
  next_follow_up_at?: string | null;
  archived_at?: string | null;
  custom_fields?: Record<string, CustomFieldValue>;
}

export interface CreateLeadPayload {
  title: string;
  company: string;
  contact_name: string;
  email: string;
  phone?: string;
  website?: string;
  industry?: string;
  company_size?: string;
  country?: string;
  state?: string;
  city?: string;
  address?: string;
  postal_code?: string;
  status?: string;
  source?: string;
  score?: number;
  assigned_to?: string | null;
  is_archived?: boolean;
  organization_id?: string;
  custom_fields?: Record<string, CustomFieldValue>;
  next_follow_up_at?: string | null;
}

export interface UpdateLeadPayload {
  title?: string;
  company?: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  website?: string;
  industry?: string;
  company_size?: string;
  country?: string;
  state?: string;
  city?: string;
  address?: string;
  postal_code?: string;
  status?: string;
  source?: string;
  score?: number;
  assigned_to?: string | null;
  is_archived?: boolean;
  organization_id?: string;
  custom_fields?: Record<string, CustomFieldValue>;
  next_follow_up_at?: string | null;
}

export interface FetchLeadsParams {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
}

export interface LeadsPage {
  items: Lead[];
  total: number;
}

export interface LeadNoteItem {
  id: string;
  entity_type: string;
  entity_id: string;
  content: string;
  created_by: string;
  created_at: string;
}

export interface LeadTaskItem {
  id: string;
  title: string;
  description?: string;
  priority?: string;
  due_date?: string;
  status?: string;
  assigned_to?: string;
  created_at: string;
}

export interface LeadEmailItem {
  id: string;
  from_email: string;
  to: string[];
  subject: string;
  body?: string | null;
  status: 'Draft' | 'Pending' | 'Processing' | 'Sent' | 'Failed' | 'Unknown';
  sent_at: string | null;
  failure_reason?: string | null;
}

export type LeadCallLogItem = CallLogItem;

export interface LeadDocumentItem {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  download_url: string;
  uploaded_at: string;
}

export interface LeadTimelineEvent {
  id: string;
  event_type: string;
  title: string;
  description: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Raw API Functions
// ---------------------------------------------------------------------------

export async function fetchLeadsApi(params: FetchLeadsParams = {}): Promise<LeadsPage> {
  const query = new URLSearchParams();
  const page = params.page ?? 1;
  const limit = params.limit ?? 15;
  query.append('page', String(page));
  query.append('limit', String(limit));
  if (params.search) query.append('search', params.search);
  if (params.status) query.append('status', params.status);

  const queryString = query.toString();
  const endpoint = `/leads${queryString ? `?${queryString}` : ''}`;
  const response = await apiClient.getWithMetadata<Lead[]>(endpoint);
  const totalHeader = response.headers.get('X-Total-Count');
  const total = totalHeader === null ? Number.NaN : Number.parseInt(totalHeader, 10);

  if (!Number.isInteger(total) || total < 0) {
    throw new Error('Leads response is missing valid pagination metadata.');
  }

  return { items: response.data, total };
}

export async function getLeadByIdApi(id: string): Promise<Lead> {
  return apiClient.get<Lead>(`/leads/${id}`);
}

export async function fetchLeadTimelineApi(leadId: string, page = 1, limit = 15): Promise<PaginatedResult<LeadTimelineEvent>> {
  return fetchPaginated<LeadTimelineEvent>(`/leads/${leadId}/timeline?page=${page}&limit=${limit}`);
}

export async function createLeadApi(payload: CreateLeadPayload): Promise<Lead> {
  return apiClient.post<Lead>('/leads', payload);
}

export async function updateLeadApi(id: string, payload: UpdateLeadPayload): Promise<Lead> {
  return apiClient.put<Lead>(`/leads/${id}`, payload);
}

export async function deleteLeadApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/leads/${id}`);
}

// Sub-resource APIs
export async function fetchLeadNotesApi(leadId: string, page = 1, limit = 15): Promise<PaginatedResult<LeadNoteItem>> {
  return fetchPaginated<LeadNoteItem>(`/leads/${leadId}/notes?page=${page}&limit=${limit}`);
}

export async function addLeadNoteApi(leadId: string, content: string): Promise<LeadNoteItem> {
  return apiClient.post<LeadNoteItem>(`/leads/${leadId}/notes?content=${encodeURIComponent(content)}`);
}

export async function fetchLeadTasksApi(leadId: string, page = 1, limit = 15): Promise<PaginatedResult<LeadTaskItem>> {
  return fetchPaginated<LeadTaskItem>(`/leads/${leadId}/tasks?page=${page}&limit=${limit}`);
}

export async function createLeadTaskApi(leadId: string, payload: { title: string; description?: string; priority?: string; due_date?: string; status?: string }): Promise<LeadTaskItem> {
  return apiClient.post<LeadTaskItem>(`/leads/${leadId}/tasks`, payload);
}

export async function fetchLeadEmailsApi(leadId: string, page = 1, limit = 15): Promise<PaginatedResult<LeadEmailItem>> {
  return fetchPaginated<LeadEmailItem>(`/leads/${leadId}/emails?page=${page}&limit=${limit}`);
}

export async function sendLeadEmailApi(
  leadId: string,
  payload: { to: string[]; subject: string; body: string },
  idempotencyKey?: string,
): Promise<LeadEmailItem> {
  return apiClient.post<LeadEmailItem>(`/leads/${leadId}/emails/send`, payload, {
    headers: { 'Idempotency-Key': idempotencyKey ?? crypto.randomUUID() },
  });
}

export async function fetchLeadCallsApi(leadId: string, page = 1, limit = 15): Promise<PaginatedResult<LeadCallLogItem>> {
  return fetchPaginated<LeadCallLogItem>(`/leads/${leadId}/calls?page=${page}&limit=${limit}`);
}

export async function logLeadCallApi(
  leadId: string,
  payload: CallLogBasePayload,
  idempotencyKey?: string,
): Promise<LeadCallLogItem> {
  return apiClient.post<LeadCallLogItem>(`/leads/${leadId}/calls`, payload, {
    headers: { 'Idempotency-Key': idempotencyKey ?? crypto.randomUUID() },
  });
}

export async function updateLeadCallApi(
  callId: string,
  payload: CallLogUpdatePayload,
): Promise<LeadCallLogItem> {
  return updateCallApi(callId, payload);
}

export async function deleteLeadCallApi(
  callId: string,
): Promise<{ message: string; status: string }> {
  return deleteCallApi(callId);
}

export async function fetchLeadDocumentsApi(leadId: string, page = 1, limit = 15): Promise<PaginatedResult<LeadDocumentItem>> {
  return fetchPaginated<LeadDocumentItem>(`/leads/${leadId}/documents?page=${page}&limit=${limit}`);
}

export async function uploadLeadDocumentApi(leadId: string, file: File): Promise<LeadDocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post<LeadDocumentItem>(`/leads/${leadId}/documents`, formData);
}

export interface LeadIntelligenceResult {
  lead_id: string;
  score: number;
  conversion_probability: number;
  quality: 'Hot' | 'Warm' | 'Cold';
  qualification: 'Qualified' | 'Needs Review' | 'Unqualified';
  confidence: number;
  reasons: string[];
  recommended_owner_id?: string | null;
  run_id?: string | null;
}

export async function recalculateLeadScoreApi(leadId: string): Promise<LeadIntelligenceResult> {
  return apiClient.post<LeadIntelligenceResult>(`/leads/${leadId}/score`);
}

export async function convertLeadApi(leadId: string, payload: { create_deal?: boolean; deal_title?: string; deal_amount?: number }): Promise<{ message: string; contact_id: string; company_id: string; deal_id: string | null }> {
  return apiClient.post(`/leads/${leadId}/convert`, payload);
}

export async function qualifyLeadApi(leadId: string, reason?: string): Promise<Lead> {
  return apiClient.post<Lead>(`/leads/${leadId}/qualify`, { reason: reason || null });
}

export async function disqualifyLeadApi(leadId: string, reason: string): Promise<Lead> {
  return apiClient.post<Lead>(`/leads/${leadId}/disqualify`, { reason });
}

export async function reopenLeadApi(leadId: string): Promise<Lead> {
  return apiClient.post<Lead>(`/leads/${leadId}/reopen`);
}

export async function assignLeadApi(leadId: string, userId: string | null): Promise<{ message: string; status: string }> {
  const suffix = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  return apiClient.post(`/leads/${leadId}/assign${suffix}`);
}

export async function archiveLeadApi(leadId: string): Promise<{ message: string; status: string }> {
  return apiClient.post(`/leads/${leadId}/archive`);
}

export async function unarchiveLeadApi(leadId: string): Promise<{ message: string; status: string }> {
  return apiClient.post(`/leads/${leadId}/unarchive`);
}

export async function bulkDeleteLeadsApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post('/leads/bulk/delete', { ids });
}

export async function bulkArchiveLeadsApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post('/leads/bulk/archive', { ids });
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useLeadsQuery(params: FetchLeadsParams = {}) {
  return useQuery({
    queryKey: ['leads', params],
    queryFn: () => fetchLeadsApi(params),
    placeholderData: (previousData) => previousData,
  });
}

export function useLeadQuery(id: string) {
  return useQuery({
    queryKey: ['lead', id],
    queryFn: () => getLeadByIdApi(id),
    enabled: !!id,
  });
}

export function useLeadTimelineQuery(leadId: string, page = 1, limit = 15) {
  return useQuery({
    queryKey: ['lead-timeline', leadId, page, limit],
    queryFn: () => fetchLeadTimelineApi(leadId, page, limit),
    enabled: !!leadId,
  });
}

export function useLeadNotesQuery(leadId: string, page = 1, limit = 15) {
  return useQuery({
    queryKey: ['lead-notes', leadId, page, limit],
    queryFn: () => fetchLeadNotesApi(leadId, page, limit),
    enabled: !!leadId,
  });
}

export function useLeadTasksQuery(leadId: string, page = 1, limit = 15) {
  return useQuery({
    queryKey: ['lead-tasks', leadId, page, limit],
    queryFn: () => fetchLeadTasksApi(leadId, page, limit),
    enabled: !!leadId,
  });
}

export function useLeadEmailsQuery(leadId: string, page = 1, limit = 15) {
  return useQuery({
    queryKey: ['lead-emails', leadId, page, limit],
    queryFn: () => fetchLeadEmailsApi(leadId, page, limit),
    enabled: !!leadId,
    refetchInterval: (query) => {
      const emails = query.state.data?.items ?? [];
      return emails.some((email) => email.status === 'Pending' || email.status === 'Processing')
        ? 5000
        : false;
    },
  });
}

export function useLeadCallsQuery(leadId: string, enabled = true, page = 1, limit = 15) {
  return useQuery({
    queryKey: ['lead-calls', leadId, page, limit],
    queryFn: () => fetchLeadCallsApi(leadId, page, limit),
    enabled: !!leadId && enabled,
  });
}

export function useLeadDocumentsQuery(leadId: string, page = 1, limit = 15) {
  return useQuery({
    queryKey: ['lead-documents', leadId, page, limit],
    queryFn: () => fetchLeadDocumentsApi(leadId, page, limit),
    enabled: !!leadId,
  });
}

export function useCreateLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateLeadPayload) => createLeadApi(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useUpdateLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateLeadPayload }) => updateLeadApi(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useDeleteLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteLeadApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useBulkDeleteLeadsMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ids: string[]) => bulkDeleteLeadsApi(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useBulkArchiveLeadsMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ids: string[]) => bulkArchiveLeadsApi(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useArchiveLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => archiveLeadApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useUnarchiveLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => unarchiveLeadApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

export function useAssignLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ leadId, userId }: { leadId: string; userId: string }) => assignLeadApi(leadId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}
