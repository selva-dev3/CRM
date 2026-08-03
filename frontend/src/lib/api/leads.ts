import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface Lead {
  id: string;
  title: string;
  company: string;
  contact_name: string;
  email: string;
  phone?: string;
  status: string;
  source: string;
  score?: number;
  organization_id?: string;
  created_at?: string;
}

export interface CreateLeadPayload {
  title: string;
  company: string;
  contact_name: string;
  email: string;
  phone?: string;
  status?: string;
  source?: string;
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

export async function createLeadApi(payload: CreateLeadPayload): Promise<Lead> {
  return apiClient.post<Lead>('/leads', payload);
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
