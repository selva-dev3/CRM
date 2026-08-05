import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface CalendarEventItem {
  id: string;
  title: string;
  start: string;
  end: string;
  event_type: string;
  description?: string;
}

export interface CalendarEventCreatePayload {
  title: string;
  start: string;
  end: string;
  event_type?: string;
  description?: string;
}

export interface AvailabilityResponse {
  user_id: string;
  date: string;
  available_slots: string[];
}

export interface RecurringEventRule {
  id: string;
  title: string;
  rrule: string;
  event_type: string;
}

export interface MessageResponse {
  message: string;
  status: string;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchCalendarEventsApi(params?: { start_date?: string; end_date?: string; search?: string }): Promise<CalendarEventItem[]> {
  const query = new URLSearchParams();
  if (params?.start_date) query.append('start_date', params.start_date);
  if (params?.end_date) query.append('end_date', params.end_date);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/calendar/events${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<CalendarEventItem[]>(endpoint);
}

export async function createCalendarEventApi(payload: CalendarEventCreatePayload): Promise<CalendarEventItem> {
  return apiClient.post<CalendarEventItem>('/calendar/events', payload);
}

export async function fetchCalendarEventApi(eventId: string): Promise<CalendarEventItem> {
  return apiClient.get<CalendarEventItem>(`/calendar/events/${eventId}`);
}

export async function updateCalendarEventApi(eventId: string, payload: CalendarEventCreatePayload): Promise<CalendarEventItem> {
  return apiClient.put<CalendarEventItem>(`/calendar/events/${eventId}`, payload);
}

export async function deleteCalendarEventApi(eventId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/calendar/events/${eventId}`);
}

export async function fetchAvailabilityApi(user_id?: string, date?: string): Promise<AvailabilityResponse> {
  const query = new URLSearchParams();
  if (user_id) query.append('user_id', user_id);
  if (date) query.append('date', date);
  return apiClient.get<AvailabilityResponse>(`/calendar/availability${query.toString() ? `?${query.toString()}` : ''}`);
}

export async function syncGoogleCalendarApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/calendar/sync/google');
}

export async function syncOutlookCalendarApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/calendar/sync/outlook');
}

export async function fetchRecurringEventsApi(): Promise<RecurringEventRule[]> {
  return apiClient.get<RecurringEventRule[]>('/calendar/recurring');
}

export async function createRecurringEventApi(title: string, rrule: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/calendar/recurring?title=${encodeURIComponent(title)}&rrule=${encodeURIComponent(rrule)}`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useCalendarEventsQuery(params?: { start_date?: string; end_date?: string; search?: string }, options?: Omit<UseQueryOptions<CalendarEventItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<CalendarEventItem[]>({
    queryKey: ['calendar', 'events', params],
    queryFn: () => fetchCalendarEventsApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useCalendarEventQuery(eventId: string, options?: Omit<UseQueryOptions<CalendarEventItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<CalendarEventItem>({
    queryKey: ['calendar', 'events', eventId],
    queryFn: () => fetchCalendarEventApi(eventId),
    enabled: !!eventId,
    ...options,
  });
}

export function useAvailabilityQuery(user_id?: string, date?: string, options?: Omit<UseQueryOptions<AvailabilityResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<AvailabilityResponse>({
    queryKey: ['calendar', 'availability', user_id, date],
    queryFn: () => fetchAvailabilityApi(user_id, date),
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRecurringEventsQuery(options?: Omit<UseQueryOptions<RecurringEventRule[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RecurringEventRule[]>({
    queryKey: ['calendar', 'recurring'],
    queryFn: fetchRecurringEventsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useCreateCalendarEventMutation(options?: UseMutationOptions<CalendarEventItem, Error, CalendarEventCreatePayload>) {
  const queryClient = useQueryClient();
  return useMutation<CalendarEventItem, Error, CalendarEventCreatePayload>({
    mutationFn: createCalendarEventApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] });
    },
    ...options,
  });
}

export function useUpdateCalendarEventMutation(options?: UseMutationOptions<CalendarEventItem, Error, { id: string; payload: CalendarEventCreatePayload }>) {
  const queryClient = useQueryClient();
  return useMutation<CalendarEventItem, Error, { id: string; payload: CalendarEventCreatePayload }>({
    mutationFn: ({ id, payload }) => updateCalendarEventApi(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] });
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events', variables.id] });
    },
    ...options,
  });
}

export function useDeleteCalendarEventMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteCalendarEventApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] });
    },
    ...options,
  });
}

export function useSyncGoogleCalendarMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: syncGoogleCalendarApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] });
    },
    ...options,
  });
}

export function useSyncOutlookCalendarMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: syncOutlookCalendarApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] });
    },
    ...options,
  });
}

export function useCreateRecurringEventMutation(options?: UseMutationOptions<MessageResponse, Error, { title: string; rrule: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { title: string; rrule: string }>({
    mutationFn: ({ title, rrule }) => createRecurringEventApi(title, rrule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'recurring'] });
    },
    ...options,
  });
}
