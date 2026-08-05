import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface RoleItem {
  id: string;
  name: string;
  description?: string;
  permissions?: string[];
  is_system_role?: boolean;
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

export async function fetchRolesApi(): Promise<RoleItem[]> {
  return apiClient.get<RoleItem[]>('/roles');
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

export async function fetchRoleUsersApi(roleId: string): Promise<UserRoleAssignment[]> {
  return apiClient.get<UserRoleAssignment[]>(`/roles/${roleId}/users`);
}

export async function checkPermissionApi(userId: string, permission: string): Promise<{ user_id: string; permission: string; allowed: boolean }> {
  return apiClient.post<{ user_id: string; permission: string; allowed: boolean }>(`/roles/check-permission?user_id=${encodeURIComponent(userId)}&permission=${encodeURIComponent(permission)}`);
}

export async function bulkDeleteRolesApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/roles/bulk-delete', { ids });
}

export async function fetchRoleAuditLogsApi(): Promise<RoleAuditLog[]> {
  return apiClient.get<RoleAuditLog[]>('/roles/audit-logs');
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

export function useRolesQuery(options?: Omit<UseQueryOptions<RoleItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleItem[]>({
    queryKey: ['roles'],
    queryFn: fetchRolesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRoleQuery(roleId: string, options?: Omit<UseQueryOptions<RoleItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleItem>({
    queryKey: ['roles', roleId],
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

export function useRoleAuditLogsQuery(options?: Omit<UseQueryOptions<RoleAuditLog[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RoleAuditLog[]>({
    queryKey: ['roles', 'audit-logs'],
    queryFn: fetchRoleAuditLogsApi,
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useRoleUsersQuery(roleId: string, options?: Omit<UseQueryOptions<UserRoleAssignment[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<UserRoleAssignment[]>({
    queryKey: ['roles', roleId, 'users'],
    queryFn: () => fetchRoleUsersApi(roleId),
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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['roles', variables.id] });
    },
    ...options,
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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['roles', variables.roleId] });
    },
    ...options,
  });
}

export function useAssignRoleToUserMutation(options?: UseMutationOptions<MessageResponse, Error, { userId: string; roleId: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { userId: string; roleId: string }>({
    mutationFn: ({ userId, roleId }) => assignRoleToUserApi(userId, roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    ...options,
  });
}

export function useRemovePermissionMutation(options?: UseMutationOptions<MessageResponse, Error, { roleId: string; permId: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { roleId: string; permId: string }>({
    mutationFn: ({ roleId, permId }) => removePermissionApi(roleId, permId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['roles', variables.roleId] });
    },
    ...options,
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
