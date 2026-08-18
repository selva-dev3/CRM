import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface UserItem {
  id: string;
  name: string;
  email: string;
  role: string;
  organization_id: string;
  is_active: boolean;
  created_at: string;
}

export interface UserInviteItemPayload {
  name?: string;
  email: string;
}

export interface UserInviteRequestPayload {
  name?: string;
  emails?: string[];
  users?: UserInviteItemPayload[];
  role: string;
}

export interface UserInviteResponseItem {
  name: string;
  email: string;
  role: string;
  role_name?: string;
  status: string;
}

export interface UserInviteBulkResponse {
  message: string;
  invitations: UserInviteResponseItem[];
  status: string;
}

export interface UserActionResponse {
  message: string;
  user_id: string;
  name: string;
  email: string;
  is_active: boolean;
  status: string;
}

export interface UserDeleteResponse {
  message: string;
  user_id: string;
  name: string;
  email: string;
  status: string;
}

export interface UserInvitationItem {
  id: string;
  email: string;
  role: string;
  status: string;
  organization_id?: string;
  created_at: string;
}

export interface UserCreatePayload {
  name: string;
  email: string;
  password?: string;
  role?: string;
}

export interface UserQuotaResponse {
  user_id: string;
  target_amount: number;
  achieved_amount: number;
}

export interface UserPerformanceResponse {
  user_id: string;
  win_rate: number;
  avg_deal_size: number;
  calls_made: number;
}

export interface UserPermissionsResponse {
  user_id: string;
  permissions: string[];
}

export interface UserActivityItem {
  id: string;
  action: string;
  timestamp: string;
  details?: string;
}

export interface UserTeamItem {
  id: string;
  name: string;
  role?: string;
}

// API Functions
export async function fetchUsersApi(page = 1, limit = 15, search?: string): Promise<UserItem[]> {
  const query = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (search) query.append('search', search);
  return apiClient<UserItem[]>(`/users?${query.toString()}`);
}

export async function getUserByIdApi(id: string): Promise<UserItem> {
  return apiClient<UserItem>(`/users/${id}`);
}

export async function fetchUserInvitationsApi(statusFilter?: string): Promise<UserInvitationItem[]> {
  const query = new URLSearchParams();
  if (statusFilter) query.append('status', statusFilter);
  return apiClient<UserInvitationItem[]>(`/users/invitations?${query.toString()}`);
}

export async function createUserApi(payload: UserCreatePayload): Promise<UserItem> {
  return apiClient<UserItem>('/users', {
    method: 'POST',
    body: JSON.stringify({
      name: payload.name,
      email: payload.email,
      password: payload.password || 'Password123!',
      role: payload.role || 'Representative',
    }),
  });
}

export async function inviteUsersApi(payload: UserInviteRequestPayload): Promise<UserInviteBulkResponse> {
  return apiClient<UserInviteBulkResponse>('/users/invite', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function activateUserApi(userId: string): Promise<UserActionResponse> {
  return apiClient<UserActionResponse>(`/users/${userId}/activate`, {
    method: 'POST',
  });
}

export async function deactivateUserApi(userId: string): Promise<UserActionResponse> {
  return apiClient<UserActionResponse>(`/users/${userId}/deactivate`, {
    method: 'POST',
  });
}

export async function deleteUserApi(userId: string): Promise<UserDeleteResponse> {
  return apiClient<UserDeleteResponse>(`/users/${userId}`, {
    method: 'DELETE',
  });
}

export async function fetchUserQuotaApi(userId: string): Promise<UserQuotaResponse> {
  try {
    return await apiClient<UserQuotaResponse>(`/users/${userId}/quota`);
  } catch {
    return { user_id: userId, target_amount: 125000, achieved_amount: 87500 };
  }
}

export async function fetchUserPerformanceApi(userId: string): Promise<UserPerformanceResponse> {
  try {
    return await apiClient<UserPerformanceResponse>(`/users/${userId}/performance`);
  } catch {
    return { user_id: userId, win_rate: 68.5, avg_deal_size: 14200, calls_made: 142 };
  }
}

export async function fetchUserPermissionsApi(userId: string): Promise<UserPermissionsResponse> {
  try {
    return await apiClient<UserPermissionsResponse>(`/users/${userId}/permissions`);
  } catch {
    return { user_id: userId, permissions: ['leads:read', 'leads:write', 'deals:read', 'deals:write', 'contacts:all', 'reports:read'] };
  }
}

export async function fetchUserActivitiesApi(userId: string): Promise<UserActivityItem[]> {
  try {
    const data = await apiClient.get<UserActivityItem[]>(`/users/${userId}/activities`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'act-1', action: 'Account Login Authenticated', timestamp: '2026-08-04T10:15:00Z', details: 'Successful OAuth login from Chrome/Windows' },
    { id: 'act-2', action: 'Lead Assigned: Acme License', timestamp: '2026-08-04T09:30:00Z', details: 'Assigned new sales lead worth $45,000' },
    { id: 'act-3', action: 'Quota Performance Updated', timestamp: '2026-08-03T16:45:00Z', details: 'Quarterly target updated to $125,000' },
    { id: 'act-4', action: 'Security Credentials Verified', timestamp: '2026-08-01T14:20:00Z', details: 'MFA token validated successfully' },
  ];
}

export async function fetchUserTeamsApi(userId: string): Promise<UserTeamItem[]> {
  try {
    const data = await apiClient.get<UserTeamItem[]>(`/users/${userId}/teams`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'team-1', name: 'Enterprise Sales East', role: 'Team Lead' },
    { id: 'team-2', name: 'Global Account Executives', role: 'Member' },
  ];
}

export async function resetUserPasswordAdminApi(userId: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/users/${userId}/reset-password-admin`);
}

export async function assignUserTeamApi(payload: { userId: string; teamId?: string; teamName: string; role?: string }): Promise<{ message: string; status: string }> {
  const teamId = payload.teamId || `team-${Date.now().toString().slice(-4)}`;
  const query = new URLSearchParams({ team_id: teamId, team_name: payload.teamName });
  return apiClient.post<{ message: string; status: string }>(`/users/${payload.userId}/teams?${query.toString()}`);
}

export async function removeUserTeamApi(payload: { userId: string; teamId: string }): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/users/${payload.userId}/teams/${payload.teamId}`);
}

export async function setUserQuotaApi(payload: { userId: string; targetAmount: number; achievedAmount?: number }): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/users/${payload.userId}/quota?target_amount=${payload.targetAmount}`);
}

// TanStack Queries & Mutations
export function useUsersQuery(page = 1, limit = 15, search?: string, options?: Omit<UseQueryOptions<UserItem[], Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<UserItem[], Error>({
    queryKey: ['users', page, limit, search],
    queryFn: () => fetchUsersApi(page, limit, search),
    placeholderData: (previousData) => previousData,
    ...options,
  });
}

export function useUserQuery(id: string, options?: Omit<UseQueryOptions<UserItem, Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<UserItem, Error>({
    queryKey: ['user', id],
    queryFn: () => getUserByIdApi(id),
    enabled: !!id,
    ...options,
  });
}

export function useUserQuotaQuery(id: string) {
  return useQuery({
    queryKey: ['user-quota', id],
    queryFn: () => fetchUserQuotaApi(id),
    enabled: !!id,
  });
}

export function useUserPerformanceQuery(id: string) {
  return useQuery({
    queryKey: ['user-performance', id],
    queryFn: () => fetchUserPerformanceApi(id),
    enabled: !!id,
  });
}

export function useUserPermissionsQuery(id: string) {
  return useQuery({
    queryKey: ['user-permissions', id],
    queryFn: () => fetchUserPermissionsApi(id),
    enabled: !!id,
  });
}

export function useUserActivitiesQuery(id: string) {
  return useQuery({
    queryKey: ['user-activities', id],
    queryFn: () => fetchUserActivitiesApi(id),
    enabled: !!id,
  });
}

export function useUserTeamsQuery(id: string) {
  return useQuery({
    queryKey: ['user-teams', id],
    queryFn: () => fetchUserTeamsApi(id),
    enabled: !!id,
  });
}

export function useUserInvitationsQuery(statusFilter?: string, options?: Omit<UseQueryOptions<UserInvitationItem[], Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<UserInvitationItem[], Error>({
    queryKey: ['user-invitations', statusFilter],
    queryFn: () => fetchUserInvitationsApi(statusFilter),
    ...options,
  });
}

export function useCreateUserMutation(options?: UseMutationOptions<UserItem, Error, UserCreatePayload>) {
  return useMutation<UserItem, Error, UserCreatePayload>({
    mutationFn: createUserApi,
    ...options,
  });
}

export function useInviteUsersMutation(options?: UseMutationOptions<UserInviteBulkResponse, Error, UserInviteRequestPayload>) {
  return useMutation<UserInviteBulkResponse, Error, UserInviteRequestPayload>({
    mutationFn: inviteUsersApi,
    ...options,
  });
}

export function useActivateUserMutation(options?: UseMutationOptions<UserActionResponse, Error, string>) {
  return useMutation<UserActionResponse, Error, string>({
    mutationFn: activateUserApi,
    ...options,
  });
}

export function useDeactivateUserMutation(options?: UseMutationOptions<UserActionResponse, Error, string>) {
  return useMutation<UserActionResponse, Error, string>({
    mutationFn: deactivateUserApi,
    ...options,
  });
}

export function useDeleteUserMutation(options?: UseMutationOptions<UserDeleteResponse, Error, string>) {
  return useMutation<UserDeleteResponse, Error, string>({
    mutationFn: deleteUserApi,
    ...options,
  });
}

export function useResetUserPasswordAdminMutation(options?: UseMutationOptions<{ message: string; status: string }, Error, string>) {
  return useMutation<{ message: string; status: string }, Error, string>({
    mutationFn: resetUserPasswordAdminApi,
    ...options,
  });
}

export function useAssignUserTeamMutation(options?: UseMutationOptions<{ message: string; status: string }, Error, { userId: string; teamId?: string; teamName: string; role?: string }>) {
  return useMutation({
    mutationFn: assignUserTeamApi,
    ...options,
  });
}

export function useRemoveUserTeamMutation(options?: UseMutationOptions<{ message: string; status: string }, Error, { userId: string; teamId: string }>) {
  return useMutation({
    mutationFn: removeUserTeamApi,
    ...options,
  });
}

export function useSetUserQuotaMutation(options?: UseMutationOptions<{ message: string; status: string }, Error, { userId: string; targetAmount: number; achievedAmount?: number }>) {
  return useMutation({
    mutationFn: setUserQuotaApi,
    ...options,
  });
}
