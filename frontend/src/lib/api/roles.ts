import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';
import { notifyPermissionsInvalidated } from '@/lib/auth-session';

export interface RoleItem {
  id: string;
  name: string;
  description?: string;
  permissions?: string[];
  is_system_role?: boolean;
  type?: string;
  created_at?: string;
}

export interface PermissionItem {
  id: string;
  module: string;
  action: string;
  description: string;
  name?: string;
  key?: string;
  category?: string;
}

export interface UserRoleAssignment {
  id: string;
  name: string;
  email?: string;
  role: string;
}

export interface RoleAuditLog {
  id: string;
  action: string;
  role_name: string;
  user: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface BulkActionResponse {
  affected_count: number;
  message: string;
}

export interface MessageResponse {
  message: string;
  status: string;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchRolesApi(params?: { page?: number; limit?: number; search?: string }): Promise<PaginatedResult<RoleItem>> {
  const query = new URLSearchParams();
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.search) query.set('search', params.search);
  return fetchPaginated<RoleItem>(`/roles${query.size ? `?${query}` : ''}`);
}

export async function fetchAssignableRolesApi(search?: string): Promise<RoleItem[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  return apiClient.get<RoleItem[]>(`/roles/assignable${query}`);
}

export async function createRoleApi(payload: { name: string; description?: string; permissions?: string[] }): Promise<RoleItem> {
  return apiClient.post<RoleItem>('/roles', payload);
}

export async function fetchPermissionMatrixApi(): Promise<PermissionItem[]> {
  return apiClient.get<PermissionItem[]>('/roles/permissions/matrix');
}

export async function createPermissionApi(payload: { name: string; key: string; category?: string; description?: string }): Promise<PermissionItem> {
  return apiClient.post<PermissionItem>('/roles/permissions', payload);
}

export async function batchImportPermissionsApi(payload: Array<{ name: string; key: string; category?: string; description?: string }>): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/roles/permissions/batch-import', payload);
}

export async function fetchSystemRolesApi(): Promise<RoleItem[]> {
  return apiClient.get<RoleItem[]>('/roles/system-roles');
}

export async function fetchDefaultRoleApi(): Promise<RoleItem> {
  return apiClient.get<RoleItem>('/roles/default');
}

export async function fetchRoleApi(roleId: string): Promise<RoleItem> {
  return apiClient.get<RoleItem>(`/roles/${roleId}`);
}

export async function updateRoleApi(roleId: string, payload: { name?: string; description?: string; permissions?: string[] }): Promise<RoleItem> {
  return apiClient.put<RoleItem>(`/roles/${roleId}`, payload);
}

export async function deleteRoleApi(roleId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/roles/${roleId}`);
}

export async function cloneRoleApi(roleId: string, new_name: string): Promise<RoleItem> {
  return apiClient.post<RoleItem>(`/roles/${roleId}/clone?new_name=${encodeURIComponent(new_name)}`);
}

export async function assignPermissionsApi(roleId: string, permissions: string[]): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/roles/${roleId}/permissions`, permissions);
}

export async function removePermissionApi(roleId: string, permId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/roles/${roleId}/permissions/${permId}`);
}

export async function fetchUserRoleApi(userId: string): Promise<RoleItem> {
  return apiClient.get<RoleItem>(`/roles/users/${userId}/role`);
}

export async function assignRoleToUserApi(userId: string, roleId: string): Promise<MessageResponse> {
  return apiClient.put<MessageResponse>(`/roles/users/${userId}/role?role_id=${encodeURIComponent(roleId)}`);
}

export async function fetchRoleUsersApi(roleId: string, page = 1, limit = 15): Promise<PaginatedResult<UserRoleAssignment>> {
  return fetchPaginated<UserRoleAssignment>(`/roles/${roleId}/users?page=${page}&limit=${limit}`);
}

export async function checkPermissionApi(userId: string, permission: string): Promise<{ user_id: string; permission: string; allowed: boolean }> {
  return apiClient.post<{ user_id: string; permission: string; allowed: boolean }>(`/roles/check-permission?user_id=${encodeURIComponent(userId)}&permission=${encodeURIComponent(permission)}`);
}

export async function bulkDeleteRolesApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/roles/bulk-delete', { ids });
}

export async function fetchRoleAuditLogsApi(page = 1, limit = 20): Promise<PaginatedResult<RoleAuditLog>> {
  return fetchPaginated<RoleAuditLog>(`/roles/audit-logs?page=${page}&limit=${limit}`);
}

export async function exportRolesApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/roles/export');
}

export async function importRolesApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/roles/import');
}

export async function setDefaultRoleApi(roleId: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/roles/${roleId}/set-default`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useRolesQuery(params?: { page?: number; limit?: number; search?: string }, options?: Omit<UseQueryOptions<PaginatedResult<RoleItem>>, 'queryKey' | 'queryFn'>) {
  return useQuery<PaginatedResult<RoleItem>>({
    queryKey: ['roles', params],
    queryFn: () => fetchRolesApi(params),
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useAssignableRolesQuery(search?: string, options?: Omit<UseQueryOptions<RoleItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleItem[]>({
    queryKey: ['roles', 'assignable-list', search],
    queryFn: () => fetchAssignableRolesApi(search),
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRoleQuery(roleId: string, options?: Omit<UseQueryOptions<RoleItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleItem>({
    queryKey: ['roles', 'detail', roleId],
    queryFn: () => fetchRoleApi(roleId),
    enabled: !!roleId,
    ...options,
  });
}

export function usePermissionMatrixQuery(options?: Omit<UseQueryOptions<PermissionItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<PermissionItem[]>({
    queryKey: ['roles', 'permissions', 'matrix'],
    queryFn: fetchPermissionMatrixApi,
    staleTime: 1000 * 60 * 10,
    ...options,
  });
}

export function useCreatePermissionMutation(options?: UseMutationOptions<PermissionItem, Error, { name: string; key: string; category?: string; description?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<PermissionItem, Error, { name: string; key: string; category?: string; description?: string }>({
    mutationFn: createPermissionApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles', 'permissions', 'matrix'] });
    },
    ...options,
  });
}

export function useBatchImportPermissionsMutation(options?: UseMutationOptions<MessageResponse, Error, Array<{ name: string; key: string; category?: string; description?: string }>>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, Array<{ name: string; key: string; category?: string; description?: string }>>({
    mutationFn: batchImportPermissionsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles', 'permissions', 'matrix'] });
    },
    ...options,
  });
}

export function useSystemRolesQuery(options?: Omit<UseQueryOptions<RoleItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleItem[]>({
    queryKey: ['roles', 'system-roles'],
    queryFn: fetchSystemRolesApi,
    staleTime: 1000 * 60 * 10,
    ...options,
  });
}

export function useDefaultRoleQuery(options?: Omit<UseQueryOptions<RoleItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleItem>({
    queryKey: ['roles', 'default'],
    queryFn: fetchDefaultRoleApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRoleAuditLogsQuery(page = 1, limit = 20, options?: Omit<UseQueryOptions<PaginatedResult<RoleAuditLog>>, 'queryKey' | 'queryFn'>) {
  return useQuery<PaginatedResult<RoleAuditLog>>({
    queryKey: ['roles', 'audit-logs', page, limit],
    queryFn: () => fetchRoleAuditLogsApi(page, limit),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useRoleUsersQuery(roleId: string, options?: Omit<UseQueryOptions<PaginatedResult<UserRoleAssignment>>, 'queryKey' | 'queryFn'>, page = 1, limit = 15) {
  return useQuery<PaginatedResult<UserRoleAssignment>>({
    queryKey: ['roles', roleId, 'users', page, limit],
    queryFn: () => fetchRoleUsersApi(roleId, page, limit),
    enabled: !!roleId,
    ...options,
  });
}

export function useCreateRoleMutation(options?: UseMutationOptions<RoleItem, Error, { name: string; description?: string; permissions?: string[] }>) {
  const queryClient = useQueryClient();
  return useMutation<RoleItem, Error, { name: string; description?: string; permissions?: string[] }>({
    mutationFn: createRoleApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export function useUpdateRoleMutation(options?: UseMutationOptions<RoleItem, Error, { id: string; payload: { name?: string; description?: string; permissions?: string[] } }>) {
  const queryClient = useQueryClient();
  return useMutation<RoleItem, Error, { id: string; payload: { name?: string; description?: string; permissions?: string[] } }>({
    mutationFn: ({ id, payload }) => updateRoleApi(id, payload),
    ...options,
    onSuccess: (data, variables, context, mutation) => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['roles', 'detail', variables.id] });
      notifyPermissionsInvalidated();
      options?.onSuccess?.(data, variables, context, mutation);
    },
  });
}

export function useDeleteRoleMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteRoleApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export function useCloneRoleMutation(options?: UseMutationOptions<RoleItem, Error, { id: string; new_name: string }>) {
  const queryClient = useQueryClient();
  return useMutation<RoleItem, Error, { id: string; new_name: string }>({
    mutationFn: ({ id, new_name }) => cloneRoleApi(id, new_name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export function useAssignPermissionsMutation(options?: UseMutationOptions<MessageResponse, Error, { roleId: string; permissions: string[] }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { roleId: string; permissions: string[] }>({
    mutationFn: ({ roleId, permissions }) => assignPermissionsApi(roleId, permissions),
    ...options,
    onSuccess: (data, variables, context, mutation) => {
      queryClient.invalidateQueries({ queryKey: ['roles', 'detail', variables.roleId] });
      notifyPermissionsInvalidated();
      options?.onSuccess?.(data, variables, context, mutation);
    },
  });
}

export function useAssignRoleToUserMutation(options?: UseMutationOptions<MessageResponse, Error, { userId: string; roleId: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { userId: string; roleId: string }>({
    mutationFn: ({ userId, roleId }) => assignRoleToUserApi(userId, roleId),
    ...options,
    onSuccess: (data, variables, context, mutation) => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
      notifyPermissionsInvalidated();
      options?.onSuccess?.(data, variables, context, mutation);
    },
  });
}

export function useRemovePermissionMutation(options?: UseMutationOptions<MessageResponse, Error, { roleId: string; permId: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { roleId: string; permId: string }>({
    mutationFn: ({ roleId, permId }) => removePermissionApi(roleId, permId),
    ...options,
    onSuccess: (data, variables, context, mutation) => {
      queryClient.invalidateQueries({ queryKey: ['roles', 'detail', variables.roleId] });
      notifyPermissionsInvalidated();
      options?.onSuccess?.(data, variables, context, mutation);
    },
  });
}

export function useBulkDeleteRolesMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteRolesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export function useSetDefaultRoleMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: setDefaultRoleApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles', 'default'] });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export async function setMultipleDefaultRolesApi(roleIds: string[]): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/roles/set-defaults', { role_ids: roleIds });
}

export function useSetMultipleDefaultRolesMutation(options?: UseMutationOptions<MessageResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string[]>({
    mutationFn: setMultipleDefaultRolesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles', 'default'] });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export function useImportRolesMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: importRolesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export type RecordScope = 'all' | 'team' | 'assigned' | 'own' | 'none';
export interface RoleRecordScope { module: string; scope: RecordScope }
export function useRoleRecordScopesQuery(roleId: string) {
  return useQuery<RoleRecordScope[]>({ queryKey: ['roles','record-scopes',roleId], queryFn: () => apiClient.get<RoleRecordScope[]>(`/roles/${roleId}/record-scopes`), enabled: Boolean(roleId) });
}
export function useUpdateRoleRecordScopesMutation() {
  const queryClient=useQueryClient();
  return useMutation<RoleRecordScope[],Error,{roleId:string;scopes:RoleRecordScope[]}>({mutationFn:({roleId,scopes})=>apiClient.put<RoleRecordScope[]>(`/roles/${roleId}/record-scopes`,{scopes}),onSuccess:(_,variables)=>queryClient.invalidateQueries({queryKey:['roles','record-scopes',variables.roleId]})});
}
