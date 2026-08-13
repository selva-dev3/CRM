import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPreferences {
  email_notifications: boolean;
  webpush_notifications: boolean;
  slack_notifications: boolean;
  digest_frequency: string;
}

export interface UnreadCountResponse {
  unread_count: number;
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

export async function fetchNotificationsApi(params?: { page?: number; limit?: number; unread_only?: boolean }): Promise<NotificationItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.unread_only) query.append('unread_only', String(params.unread_only));
  const endpoint = `/notifications${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<NotificationItem[]>(endpoint);
}

export async function fetchUnreadCountApi(): Promise<UnreadCountResponse> {
  return apiClient.get<UnreadCountResponse>('/notifications/unread-count');
}

export async function markAllNotificationsReadApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/notifications/read-all');
}

export async function fetchNotificationPreferencesApi(): Promise<NotificationPreferences> {
  return apiClient.get<NotificationPreferences>('/notifications/preferences');
}

export async function updateNotificationPreferencesApi(prefs: NotificationPreferences): Promise<MessageResponse> {
  const query = new URLSearchParams({
    email_notifications: String(prefs.email_notifications),
    webpush_notifications: String(prefs.webpush_notifications),
    slack_notifications: String(prefs.slack_notifications),
    digest_frequency: prefs.digest_frequency || 'Daily',
  });
  return apiClient.put<MessageResponse>(`/notifications/preferences?${query.toString()}`);
}

export async function registerWebpushTokenApi(token: string, device_type: string = 'Chrome Desktop'): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/notifications/webpush/register?token=${encodeURIComponent(token)}&device_type=${encodeURIComponent(device_type)}`);
}

export async function sendSystemAlertApi(title: string, message: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/notifications/send-system-alert?title=${encodeURIComponent(title)}&message=${encodeURIComponent(message)}`);
}

export async function bulkDeleteNotificationsApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/notifications/bulk-delete', { ids });
}

export async function markNotificationReadApi(id: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/notifications/${id}/read`);
}

export async function deleteNotificationApi(id: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/notifications/${id}`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useNotificationsQuery(params?: { page?: number; limit?: number; unread_only?: boolean }, options?: Omit<UseQueryOptions<NotificationItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<NotificationItem[]>({
    queryKey: ['notifications', params],
    queryFn: () => fetchNotificationsApi(params),
    staleTime: 1000 * 30,
    ...options,
  });
}

export function useUnreadCountQuery(options?: Omit<UseQueryOptions<UnreadCountResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<UnreadCountResponse>({
    queryKey: ['notifications', 'unread-count'],
    queryFn: fetchUnreadCountApi,
    refetchInterval: 1000 * 30,
    ...options,
  });
}

export function useNotificationPreferencesQuery(options?: Omit<UseQueryOptions<NotificationPreferences>, 'queryKey' | 'queryFn'>) {
  return useQuery<NotificationPreferences>({
    queryKey: ['notifications', 'preferences'],
    queryFn: fetchNotificationPreferencesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useMarkAllReadMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: markAllNotificationsReadApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
    ...options,
  });
}

export function useMarkNotificationReadMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: markNotificationReadApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
    ...options,
  });
}

export function useDeleteNotificationMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteNotificationApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
    ...options,
  });
}

export function useBulkDeleteNotificationsMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteNotificationsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
    ...options,
  });
}

export function useUpdateNotificationPreferencesMutation(options?: UseMutationOptions<MessageResponse, Error, NotificationPreferences>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, NotificationPreferences>({
    mutationFn: updateNotificationPreferencesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications', 'preferences'] });
    },
    ...options,
  });
}

export function useRegisterWebpushTokenMutation(options?: UseMutationOptions<MessageResponse, Error, { token: string; device_type?: string }>) {
  return useMutation<MessageResponse, Error, { token: string; device_type?: string }>({
    mutationFn: ({ token, device_type }) => registerWebpushTokenApi(token, device_type),
    ...options,
  });
}

export function useSendSystemAlertMutation(options?: UseMutationOptions<MessageResponse, Error, { title: string; message: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { title: string; message: string }>({
    mutationFn: ({ title, message }) => sendSystemAlertApi(title, message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
    ...options,
  });
}
