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

export function useCreateLeadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateLeadPayload) => createLeadApi(payload),
    onSuccess: () => {
      // Invalidate leads query cache to refresh table automatically
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
