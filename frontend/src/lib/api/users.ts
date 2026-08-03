import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

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
  token: string;
  role: string;
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

// API Functions
export async function fetchUsersApi(page = 1, limit = 20, search?: string): Promise<UserItem[]> {
  const query = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (search) query.append('search', search);
  return apiClient<UserItem[]>(`/users?${query.toString()}`);
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

// TanStack Queries & Mutations
export function useUsersQuery(page = 1, limit = 20, search?: string, options?: Omit<UseQueryOptions<UserItem[], Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<UserItem[], Error>({
    queryKey: ['users', page, limit, search],
    queryFn: () => fetchUsersApi(page, limit, search),
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
