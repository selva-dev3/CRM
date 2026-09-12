import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

export interface ProjectItem {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  status: string;
  priority: string;
  owner_id?: string | null;
  company_id?: string | null;
  contact_id?: string | null;
  originating_deal_id?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  budget?: number | null;
  completion_percentage: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProjectPayload {
  name: string;
  description?: string | null;
  status?: string;
  priority?: string;
  owner_id?: string | null;
  company_id?: string | null;
  contact_id?: string | null;
  originating_deal_id?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  budget?: number | null;
  completion_percentage?: number;
}

export interface ProjectStakeholder {
  id: string;
  project_id: string;
  contact_id: string;
  role: string;
}

export interface FetchProjectsParams {
  page?: number;
  limit?: number;
  status?: string;
  priority?: string;
  search?: string;
}

export async function fetchProjectsPageApi(
  params: FetchProjectsParams = {},
): Promise<PaginatedResult<ProjectItem>> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    limit: String(params.limit ?? 20),
  });
  if (params.status) query.set('status', params.status);
  if (params.priority) query.set('priority', params.priority);
  if (params.search) query.set('search', params.search);
  return fetchPaginated<ProjectItem>(`/projects?${query.toString()}`);
}

export function getProjectByIdApi(id: string): Promise<ProjectItem> {
  return apiClient.get<ProjectItem>(`/projects/${encodeURIComponent(id)}`);
}

export function createProjectApi(payload: ProjectPayload): Promise<ProjectItem> {
  return apiClient.post<ProjectItem>('/projects', payload);
}

export function updateProjectApi(id: string, payload: Partial<ProjectPayload>): Promise<ProjectItem> {
  return apiClient.put<ProjectItem>(`/projects/${encodeURIComponent(id)}`, payload);
}

export function deleteProjectApi(id: string): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/projects/${encodeURIComponent(id)}`);
}

export function useProjectsPageQuery(params: FetchProjectsParams) {
  return useQuery({
    queryKey: ['projects', 'paginated', params],
    queryFn: () => fetchProjectsPageApi(params),
    placeholderData: (previousData) => previousData,
  });
}

export function useProjectQuery(id: string) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => getProjectByIdApi(id),
    enabled: Boolean(id),
  });
}

export function useProjectStakeholdersQuery(id: string, enabled = true) {
  return useQuery({
    queryKey: ['project', id, 'stakeholders'],
    queryFn: () => apiClient.get<ProjectStakeholder[]>(`/projects/${encodeURIComponent(id)}/stakeholders`),
    enabled: Boolean(id) && enabled,
  });
}

function useInvalidateProjects() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ['projects'] });
  };
}

export function useCreateProjectMutation() {
  const invalidate = useInvalidateProjects();
  return useMutation({ mutationFn: createProjectApi, onSuccess: invalidate });
}

export function useUpdateProjectMutation() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProjects();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ProjectPayload> }) => updateProjectApi(id, payload),
    onSuccess: (project) => {
      queryClient.setQueryData(['project', project.id], project);
      invalidate();
    },
  });
}

export function useDeleteProjectMutation() {
  const invalidate = useInvalidateProjects();
  return useMutation({ mutationFn: deleteProjectApi, onSuccess: invalidate });
}

export function useAddProjectStakeholderMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, contactId, role }: { projectId: string; contactId: string; role: string }) =>
      apiClient.post<ProjectStakeholder>(`/projects/${encodeURIComponent(projectId)}/stakeholders`, { contact_id: contactId, role }),
    onSuccess: (_item, variables) => queryClient.invalidateQueries({ queryKey: ['project', variables.projectId, 'stakeholders'] }),
  });
}

export function useRemoveProjectStakeholderMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, stakeholderId }: { projectId: string; stakeholderId: string }) =>
      apiClient.delete<void>(`/projects/${encodeURIComponent(projectId)}/stakeholders/${encodeURIComponent(stakeholderId)}`),
    onSuccess: (_item, variables) => queryClient.invalidateQueries({ queryKey: ['project', variables.projectId, 'stakeholders'] }),
  });
}
