import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

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
}

export interface FetchLeadsParams {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
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
  sent_at: string;
}

export interface LeadCallLogItem {
  id: string;
  contact_id: string;
  call_type: string;
  duration_seconds: number;
  notes?: string;
  timestamp: string;
}

export interface LeadDocumentItem {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  download_url: string;
  uploaded_at: string;
}

// ---------------------------------------------------------------------------
// Raw API Functions
// ---------------------------------------------------------------------------

export async function fetchLeadsApi(params: FetchLeadsParams = {}): Promise<Lead[]> {
  const query = new URLSearchParams();
  if (params.page) query.append('page', String(params.page));
  if (params.limit) query.append('limit', String(params.limit));
  if (params.search) query.append('search', params.search);
  if (params.status) query.append('status', params.status);

  const queryString = query.toString();
  const endpoint = `/leads${queryString ? `?${queryString}` : ''}`;
  return apiClient.get<Lead[]>(endpoint);
}

export async function getLeadByIdApi(id: string): Promise<Lead> {
  return apiClient.get<Lead>(`/leads/${id}`);
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
export async function fetchLeadNotesApi(leadId: string): Promise<LeadNoteItem[]> {
  return apiClient.get<LeadNoteItem[]>(`/leads/${leadId}/notes`);
}

export async function addLeadNoteApi(leadId: string, content: string): Promise<LeadNoteItem> {
  return apiClient.post<LeadNoteItem>(`/leads/${leadId}/notes?content=${encodeURIComponent(content)}`);
}

export async function fetchLeadTasksApi(leadId: string): Promise<LeadTaskItem[]> {
  return apiClient.get<LeadTaskItem[]>(`/leads/${leadId}/tasks`);
}

export async function createLeadTaskApi(leadId: string, payload: { title: string; description?: string; priority?: string; due_date?: string; status?: string }): Promise<LeadTaskItem> {
  return apiClient.post<LeadTaskItem>(`/leads/${leadId}/tasks`, payload);
}

export async function fetchLeadEmailsApi(leadId: string): Promise<LeadEmailItem[]> {
  return apiClient.get<LeadEmailItem[]>(`/leads/${leadId}/emails`);
}

export async function sendLeadEmailApi(leadId: string, payload: { to: string[]; subject: string; body: string }): Promise<LeadEmailItem> {
  return apiClient.post<LeadEmailItem>(`/leads/${leadId}/emails/send`, payload);
}

export async function fetchLeadCallsApi(leadId: string): Promise<LeadCallLogItem[]> {
  return apiClient.get<LeadCallLogItem[]>(`/leads/${leadId}/calls`);
}

export async function logLeadCallApi(leadId: string, payload: { call_type: string; duration_seconds: number; notes?: string }): Promise<LeadCallLogItem> {
  return apiClient.post<LeadCallLogItem>(`/leads/${leadId}/calls`, payload);
}

export async function fetchLeadDocumentsApi(leadId: string): Promise<LeadDocumentItem[]> {
  return apiClient.get<LeadDocumentItem[]>(`/leads/${leadId}/documents`);
}

export async function recalculateLeadScoreApi(leadId: string): Promise<{ old_score: number; new_score: number; factors: string[] }> {
  return apiClient.post<{ old_score: number; new_score: number; factors: string[] }>(`/leads/${leadId}/score`);
}

export async function convertLeadApi(leadId: string, payload: { create_deal?: boolean; deal_title?: string; deal_amount?: number }): Promise<{ message: string; contact_id: string; company_id: string; deal_id: string }> {
  return apiClient.post(`/leads/${leadId}/convert`, payload);
}

export async function assignLeadApi(leadId: string, userId: string): Promise<{ message: string; status: string }> {
  return apiClient.post(`/leads/${leadId}/assign?user_id=${encodeURIComponent(userId)}`);
}

export async function archiveLeadApi(leadId: string): Promise<{ message: string; status: string }> {
  return apiClient.post(`/leads/${leadId}/archive`);
}

export async function unarchiveLeadApi(leadId: string): Promise<{ message: string; status: string }> {
  return apiClient.post(`/leads/${leadId}/unarchive`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useLeadsQuery(params: FetchLeadsParams = {}) {
  return useQuery({
    queryKey: ['leads', params],
    queryFn: () => fetchLeadsApi(params),
  });
}

export function useLeadQuery(id: string) {
  return useQuery({
    queryKey: ['lead', id],
    queryFn: () => getLeadByIdApi(id),
    enabled: !!id,
  });
}

export function useLeadNotesQuery(leadId: string) {
  return useQuery({
    queryKey: ['lead-notes', leadId],
    queryFn: () => fetchLeadNotesApi(leadId),
    enabled: !!leadId,
  });
}

export function useLeadTasksQuery(leadId: string) {
  return useQuery({
    queryKey: ['lead-tasks', leadId],
    queryFn: () => fetchLeadTasksApi(leadId),
    enabled: !!leadId,
  });
}

export function useLeadEmailsQuery(leadId: string) {
  return useQuery({
    queryKey: ['lead-emails', leadId],
    queryFn: () => fetchLeadEmailsApi(leadId),
    enabled: !!leadId,
  });
}

export function useLeadCallsQuery(leadId: string) {
  return useQuery({
    queryKey: ['lead-calls', leadId],
    queryFn: () => fetchLeadCallsApi(leadId),
    enabled: !!leadId,
  });
}

export function useLeadDocumentsQuery(leadId: string) {
  return useQuery({
    queryKey: ['lead-documents', leadId],
    queryFn: () => fetchLeadDocumentsApi(leadId),
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
