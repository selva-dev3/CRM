import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface MeetingItem {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  attendees?: string[];
  meeting_link?: string;
  ai_summary?: string;
}

export interface MeetingCreatePayload {
  title: string;
  start_time: string;
  end_time: string;
  attendee_emails: string[];
  meeting_link?: string;
}

export interface MeetingUpdatePayload {
  title?: string;
  start_time?: string;
  end_time?: string;
  attendees?: string[];
  meeting_link?: string;
}

export interface BulkActionResponse {
  affected_count: number;
  message: string;
}

export interface MessageResponse {
  message: string;
  status: string;
}

export interface ZoomLinkResponse {
  join_url: string;
  start_url: string;
  topic?: string;
}

export interface TeamsLinkResponse {
  join_url: string;
  subject?: string;
}

export interface AiSummaryResponse {
  meeting_id: string;
  summary: string | null;
  key_decisions: string[];
}

export interface ActionItem {
  id: string;
  task: string;
  assignee?: string | null;
  status: string;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchMeetingsApi(params?: { page?: number; limit?: number; search?: string }): Promise<MeetingItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.search) query.append('search', params.search);
  const endpoint = `/meetings${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<MeetingItem[]>(endpoint);
}

export async function createMeetingApi(payload: MeetingCreatePayload): Promise<MeetingItem> {
  return apiClient.post<MeetingItem>('/meetings', payload);
}

export async function fetchUpcomingMeetingsApi(): Promise<MeetingItem[]> {
  return apiClient.get<MeetingItem[]>('/meetings/upcoming');
}

export async function createZoomLinkApi(topic?: string, start_time?: string): Promise<ZoomLinkResponse> {
  return apiClient.post<ZoomLinkResponse>(`/meetings/zoom/create-link?topic=${encodeURIComponent(topic || 'CRM Meeting')}&start_time=${encodeURIComponent(start_time || '')}`);
}

export async function createTeamsLinkApi(subject?: string, start_time?: string): Promise<TeamsLinkResponse> {
  return apiClient.post<TeamsLinkResponse>(`/meetings/teams/create-link?subject=${encodeURIComponent(subject || 'CRM Meeting')}&start_time=${encodeURIComponent(start_time || '')}`);
}

export async function exportIcalFeedApi(): Promise<{ ical_url: string }> {
  return apiClient.get<{ ical_url: string }>('/meetings/export/ical');
}

export async function bulkCancelMeetingsApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/meetings/bulk-cancel', { ids });
}

export async function fetchMeetingApi(meetingId: string): Promise<MeetingItem> {
  return apiClient.get<MeetingItem>(`/meetings/${meetingId}`);
}

export async function updateMeetingApi(meetingId: string, payload: MeetingUpdatePayload): Promise<MeetingItem> {
  return apiClient.put<MeetingItem>(`/meetings/${meetingId}`, payload);
}

export async function cancelMeetingApi(meetingId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/meetings/${meetingId}`);
}

export async function rescheduleMeetingApi(meetingId: string, new_start_time: string, new_end_time: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/meetings/${meetingId}/reschedule?new_start_time=${encodeURIComponent(new_start_time)}&new_end_time=${encodeURIComponent(new_end_time)}`);
}

export async function meetingRsvpApi(meetingId: string, email: string, response: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/meetings/${meetingId}/rsvp?email=${encodeURIComponent(email)}&response=${encodeURIComponent(response)}`);
}

export async function uploadMeetingTranscriptApi(meetingId: string, transcript_text: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/meetings/${meetingId}/transcript`, {
    transcript: transcript_text,
  });
}

export async function fetchMeetingAiSummaryApi(meetingId: string): Promise<AiSummaryResponse> {
  return apiClient.get<AiSummaryResponse>(`/meetings/${meetingId}/ai-summary`);
}

export async function fetchMeetingActionItemsApi(meetingId: string): Promise<ActionItem[]> {
  return apiClient.get<ActionItem[]>(`/meetings/${meetingId}/action-items`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useMeetingsQuery(params?: { page?: number; limit?: number; search?: string }, options?: Omit<UseQueryOptions<MeetingItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<MeetingItem[]>({
    queryKey: ['meetings', params],
    queryFn: () => fetchMeetingsApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useUpcomingMeetingsQuery(options?: Omit<UseQueryOptions<MeetingItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<MeetingItem[]>({
    queryKey: ['meetings', 'upcoming'],
    queryFn: fetchUpcomingMeetingsApi,
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useMeetingQuery(meetingId: string, options?: Omit<UseQueryOptions<MeetingItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<MeetingItem>({
    queryKey: ['meetings', meetingId],
    queryFn: () => fetchMeetingApi(meetingId),
    enabled: !!meetingId,
    ...options,
  });
}

export function useMeetingAiSummaryQuery(meetingId: string, options?: Omit<UseQueryOptions<AiSummaryResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<AiSummaryResponse>({
    queryKey: ['meetings', meetingId, 'ai-summary'],
    queryFn: () => fetchMeetingAiSummaryApi(meetingId),
    enabled: !!meetingId,
    ...options,
  });
}

export function useMeetingActionItemsQuery(meetingId: string, options?: Omit<UseQueryOptions<ActionItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<ActionItem[]>({
    queryKey: ['meetings', meetingId, 'action-items'],
    queryFn: () => fetchMeetingActionItemsApi(meetingId),
    enabled: !!meetingId,
    ...options,
  });
}

export function useCreateMeetingMutation(options?: UseMutationOptions<MeetingItem, Error, MeetingCreatePayload>) {
  const queryClient = useQueryClient();
  return useMutation<MeetingItem, Error, MeetingCreatePayload>({
    mutationFn: createMeetingApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
    },
    ...options,
  });
}

export function useUpdateMeetingMutation(options?: UseMutationOptions<MeetingItem, Error, { id: string; payload: MeetingUpdatePayload }>) {
  const queryClient = useQueryClient();
  return useMutation<MeetingItem, Error, { id: string; payload: MeetingUpdatePayload }>({
    mutationFn: ({ id, payload }) => updateMeetingApi(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      queryClient.invalidateQueries({ queryKey: ['meetings', variables.id] });
    },
    ...options,
  });
}

export function useCancelMeetingMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: cancelMeetingApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
    },
    ...options,
  });
}

export function useBulkCancelMeetingsMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkCancelMeetingsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
    },
    ...options,
  });
}

export function useCreateZoomLinkMutation(options?: UseMutationOptions<ZoomLinkResponse, Error, { topic?: string; start_time?: string }>) {
  return useMutation<ZoomLinkResponse, Error, { topic?: string; start_time?: string }>({
    mutationFn: ({ topic, start_time }) => createZoomLinkApi(topic, start_time),
    ...options,
  });
}

export function useCreateTeamsLinkMutation(options?: UseMutationOptions<TeamsLinkResponse, Error, { subject?: string; start_time?: string }>) {
  return useMutation<TeamsLinkResponse, Error, { subject?: string; start_time?: string }>({
    mutationFn: ({ subject, start_time }) => createTeamsLinkApi(subject, start_time),
    ...options,
  });
}

export function useRescheduleMeetingMutation(options?: UseMutationOptions<MessageResponse, Error, { meetingId: string; new_start_time: string; new_end_time: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { meetingId: string; new_start_time: string; new_end_time: string }>({
    mutationFn: ({ meetingId, new_start_time, new_end_time }) => rescheduleMeetingApi(meetingId, new_start_time, new_end_time),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      queryClient.invalidateQueries({ queryKey: ['meetings', variables.meetingId] });
    },
    ...options,
  });
}

export function useMeetingRsvpMutation(options?: UseMutationOptions<MessageResponse, Error, { meetingId: string; email: string; response: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { meetingId: string; email: string; response: string }>({
    mutationFn: ({ meetingId, email, response }) => meetingRsvpApi(meetingId, email, response),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['meetings', variables.meetingId] });
    },
    ...options,
  });
}

export function useUploadTranscriptMutation(options?: UseMutationOptions<MessageResponse, Error, { meetingId: string; transcript_text: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { meetingId: string; transcript_text: string }>({
    mutationFn: ({ meetingId, transcript_text }) => uploadMeetingTranscriptApi(meetingId, transcript_text),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['meetings', variables.meetingId] });
      queryClient.invalidateQueries({ queryKey: ['meetings', variables.meetingId, 'ai-summary'] });
    },
    ...options,
  });
}
