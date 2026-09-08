import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface CallLogItem {
  id: string;
  contact_id?: string;
  lead_id?: string;
  company_id?: string;
  deal_id?: string;
  call_type?: CallType;
  disposition?: CallDisposition | null;
  duration_seconds?: number;
  subject?: string | null;
  notes?: string | null;
  follow_up_required?: boolean;
  follow_up_at?: string | null;
  next_action?: string | null;
  created_by?: string | null;
  created_by_name?: string | null;
  timestamp?: string;
  created_at?: string;
  updated_at?: string;
}

export type CallType = 'Outbound' | 'Inbound';
export type CallDisposition = 'Completed' | 'No Answer' | 'Busy' | 'Failed' | 'Other';

export interface CallLogBasePayload {
  contact_id?: string;
  lead_id?: string;
  company_id?: string;
  deal_id?: string;
  call_type?: CallType;
  disposition?: CallDisposition;
  timestamp?: string;
  duration_seconds?: number;
  subject?: string;
  notes?: string;
  follow_up_required?: boolean;
  follow_up_at?: string | null;
  next_action?: string;
}

export type CallLogUpdatePayload = Omit<CallLogBasePayload, 'lead_id'>;

export interface OutboundCallResponse {
  call_sid: string;
  status: string;
  to: string;
  contact_id?: string;
}

export interface RepPerformanceStat {
  rep: string;
  total_calls: number;
  connected: number;
  voicemails: number;
  total_duration: number;
}

export interface RecordingResponse {
  call_id: string;
  recording_url: string;
  duration_seconds: number;
}

export interface SentimentResponse {
  call_id: string;
  overall_sentiment: 'Positive' | 'Neutral' | 'Negative';
  confidence_score: number;
  reasons: string[];
  urgency: 'Low' | 'Medium' | 'High';
  escalation_required: boolean;
  run_id?: string | null;
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

export interface FetchCallsParams {
  page?: number;
  limit?: number;
  search?: string;
  call_type?: string;
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
  deal_id?: string;
}

export async function fetchCallsApi(params?: FetchCallsParams): Promise<CallLogItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.search) query.append('search', params.search);
  if (params?.call_type) query.append('call_type', params.call_type);
  if (params?.lead_id) query.append('lead_id', params.lead_id);
  if (params?.contact_id) query.append('contact_id', params.contact_id);
  if (params?.company_id) query.append('company_id', params.company_id);
  if (params?.deal_id) query.append('deal_id', params.deal_id);
  const endpoint = `/calls${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<CallLogItem[]>(endpoint);
}

export async function logCallApi(
  payload: CallLogBasePayload,
  idempotencyKey?: string,
): Promise<CallLogItem> {
  return apiClient.post<CallLogItem>('/calls', payload, {
    headers: { 'Idempotency-Key': idempotencyKey ?? crypto.randomUUID() },
  });
}

export async function triggerOutboundCallApi(phone_number: string, contact_id: string): Promise<OutboundCallResponse> {
  return apiClient.post<OutboundCallResponse>(`/calls/trigger-outbound?phone_number=${encodeURIComponent(phone_number)}&contact_id=${encodeURIComponent(contact_id)}`);
}

export async function fetchCallDispositionsApi(): Promise<string[]> {
  return apiClient.get<string[]>('/calls/dispositions');
}

export async function createCallDispositionApi(name: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/calls/dispositions?name=${encodeURIComponent(name)}`);
}

export async function fetchRepPerformanceStatsApi(): Promise<RepPerformanceStat[]> {
  return apiClient.get<RepPerformanceStat[]>('/calls/stats/rep-performance');
}

export async function logVoicemailDropApi(contact_id: string, voicemail_template_id: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/calls/voicemail?contact_id=${encodeURIComponent(contact_id)}&voicemail_template_id=${encodeURIComponent(voicemail_template_id)}`);
}

export async function bulkDeleteCallsApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/calls/bulk-delete', { ids });
}

export async function fetchCallApi(callId: string): Promise<CallLogItem> {
  return apiClient.get<CallLogItem>(`/calls/${callId}`);
}

export async function deleteCallApi(callId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/calls/${callId}`);
}

export async function updateCallApi(
  callId: string,
  payload: CallLogUpdatePayload,
): Promise<CallLogItem> {
  return apiClient.put<CallLogItem>(`/calls/${callId}`, payload);
}

export async function fetchCallRecordingApi(callId: string): Promise<RecordingResponse> {
  return apiClient.get<RecordingResponse>(`/calls/${callId}/recording`);
}

export async function fetchCallSentimentApi(callId: string): Promise<SentimentResponse> {
  return apiClient.get<SentimentResponse>(`/calls/${callId}/sentiment`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useCallsQuery(params?: FetchCallsParams, options?: Omit<UseQueryOptions<CallLogItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<CallLogItem[]>({
    queryKey: ['calls', params],
    queryFn: () => fetchCallsApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useCallQuery(callId: string, options?: Omit<UseQueryOptions<CallLogItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<CallLogItem>({
    queryKey: ['calls', callId],
    queryFn: () => fetchCallApi(callId),
    enabled: !!callId,
    ...options,
  });
}

export function useCallDispositionsQuery(options?: Omit<UseQueryOptions<string[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<string[]>({
    queryKey: ['calls', 'dispositions'],
    queryFn: fetchCallDispositionsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useRepPerformanceStatsQuery(options?: Omit<UseQueryOptions<RepPerformanceStat[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RepPerformanceStat[]>({
    queryKey: ['calls', 'stats', 'rep-performance'],
    queryFn: fetchRepPerformanceStatsApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useCallRecordingQuery(callId: string, options?: Omit<UseQueryOptions<RecordingResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<RecordingResponse>({
    queryKey: ['calls', callId, 'recording'],
    queryFn: () => fetchCallRecordingApi(callId),
    enabled: !!callId,
    ...options,
  });
}

export function useCallSentimentQuery(callId: string, options?: Omit<UseQueryOptions<SentimentResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<SentimentResponse>({
    queryKey: ['calls', callId, 'sentiment'],
    queryFn: () => fetchCallSentimentApi(callId),
    enabled: !!callId,
    ...options,
  });
}

export function useLogCallMutation(options?: UseMutationOptions<CallLogItem, Error, CallLogBasePayload>) {
  const queryClient = useQueryClient();
  return useMutation<CallLogItem, Error, CallLogBasePayload>({
    mutationFn: (payload) => logCallApi(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calls'] });
    },
    ...options,
  });
}

export function useTriggerOutboundCallMutation(options?: UseMutationOptions<OutboundCallResponse, Error, { phone_number: string; contact_id: string }>) {
  return useMutation<OutboundCallResponse, Error, { phone_number: string; contact_id: string }>({
    mutationFn: ({ phone_number, contact_id }) => triggerOutboundCallApi(phone_number, contact_id),
    ...options,
  });
}

export function useCreateDispositionMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: createCallDispositionApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calls', 'dispositions'] });
    },
    ...options,
  });
}

export function useLogVoicemailDropMutation(options?: UseMutationOptions<MessageResponse, Error, { contact_id: string; voicemail_template_id: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { contact_id: string; voicemail_template_id: string }>({
    mutationFn: ({ contact_id, voicemail_template_id }) => logVoicemailDropApi(contact_id, voicemail_template_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calls'] });
    },
    ...options,
  });
}

export function useDeleteCallMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteCallApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calls'] });
    },
    ...options,
  });
}

export function useBulkDeleteCallsMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteCallsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calls'] });
    },
    ...options,
  });
}
