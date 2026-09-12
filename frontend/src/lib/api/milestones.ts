import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

export type MilestoneStatus = 'Pending' | 'In Progress' | 'Completed' | 'Cancelled';
export interface MilestoneItem { id: string; project_id: string; name: string; description?: string | null; status: MilestoneStatus; due_date?: string | null; completed_at?: string | null; }
export interface MilestonePayload { project_id: string; name: string; description?: string; status?: MilestoneStatus; due_date?: string; }

export function fetchMilestones(params: { page?: number; limit?: number; project_id?: string; status?: string } = {}): Promise<PaginatedResult<MilestoneItem>> {
  const query = new URLSearchParams({ page: String(params.page ?? 1), limit: String(params.limit ?? 20) });
  if (params.project_id) query.set('project_id', params.project_id);
  if (params.status) query.set('status', params.status);
  return fetchPaginated(`/milestones?${query}`);
}
export function useMilestonesQuery(params: Parameters<typeof fetchMilestones>[0]) { return useQuery({ queryKey: ['milestones', params], queryFn: () => fetchMilestones(params), placeholderData: (old) => old }); }
function useInvalidateMilestones() { const client = useQueryClient(); return () => client.invalidateQueries({ queryKey: ['milestones'] }); }
export function useCreateMilestone() { const invalidate = useInvalidateMilestones(); return useMutation({ mutationFn: (payload: MilestonePayload) => apiClient.post<MilestoneItem>('/milestones', payload), onSuccess: invalidate }); }
export function useUpdateMilestone() { const invalidate = useInvalidateMilestones(); return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: Partial<MilestonePayload> }) => apiClient.put<MilestoneItem>(`/milestones/${id}`, payload), onSuccess: invalidate }); }
export function useDeleteMilestone() { const invalidate = useInvalidateMilestones(); return useMutation({ mutationFn: (id: string) => apiClient.delete(`/milestones/${id}`), onSuccess: invalidate }); }
