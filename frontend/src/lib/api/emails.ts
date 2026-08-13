import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface EmailMessageItem {
  id: string;
  from_email: string;
  to: string[];
  subject: string;
  body?: string;
  sent_at: string;
}

export interface EmailSendPayload {
  to: string[];
  subject: string;
  body: string;
}

export interface EmailTemplateItem {
  id: string;
  name: string;
  subject: string;
  body?: string;
  category: string;
}

export interface EmailSignatureItem {
  id: string;
  name: string;
  html: string;
}

export interface EmailTrackingStatus {
  email_id: string;
  opens: number;
  last_opened_at: string | null;
  link_clicks: number;
  bounced: boolean;
}

export interface EmailThreadMessage {
  from: string;
  to: string;
  subject: string;
  body: string;
  timestamp: string;
}

export interface EmailThreadResponse {
  thread_id: string;
  messages: EmailThreadMessage[];
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

export async function fetchInboxApi(params?: { page?: number; limit?: number; folder?: string; search?: string }): Promise<EmailMessageItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.folder) query.append('folder', params.folder);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/emails/inbox${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<EmailMessageItem[]>(endpoint);
}

export async function sendEmailApi(payload: EmailSendPayload): Promise<EmailMessageItem> {
  return apiClient.post<EmailMessageItem>('/emails/send', payload);
}

export async function fetchDraftsApi(): Promise<EmailMessageItem[]> {
  return apiClient.get<EmailMessageItem[]>('/emails/drafts');
}

export async function saveDraftApi(payload: EmailSendPayload): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/emails/drafts', payload);
}

export async function fetchDraftApi(draftId: string): Promise<EmailMessageItem> {
  return apiClient.get<EmailMessageItem>(`/emails/drafts/${draftId}`);
}

export async function deleteDraftApi(draftId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/emails/drafts/${draftId}`);
}

export async function fetchEmailTemplatesApi(): Promise<EmailTemplateItem[]> {
  return apiClient.get<EmailTemplateItem[]>('/emails/templates');
}

export async function createEmailTemplateApi(name: string, subject: string, body: string, category: string = 'General'): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/emails/templates?name=${encodeURIComponent(name)}&subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}&category=${encodeURIComponent(category)}`);
}

export async function fetchEmailTemplateApi(templateId: string): Promise<EmailTemplateItem> {
  return apiClient.get<EmailTemplateItem>(`/emails/templates/${templateId}`);
}

export async function updateEmailTemplateApi(templateId: string, name: string, subject: string, body: string): Promise<MessageResponse> {
  return apiClient.put<MessageResponse>(`/emails/templates/${templateId}?name=${encodeURIComponent(name)}&subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`);
}

export async function deleteEmailTemplateApi(templateId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/emails/templates/${templateId}`);
}

export async function sendBulkCampaignApi(template_id: string, lead_ids: string[]): Promise<{ campaign_id: string; queued_count: number; status: string }> {
  return apiClient.post('/emails/campaigns/send-bulk', { template_id, lead_ids });
}

export async function fetchEmailTrackingStatusApi(emailId: string): Promise<EmailTrackingStatus> {
  return apiClient.get<EmailTrackingStatus>(`/emails/tracking/${emailId}/status`);
}

export async function fetchEmailSignaturesApi(): Promise<EmailSignatureItem[]> {
  return apiClient.get<EmailSignatureItem[]>('/emails/signatures');
}

export async function saveEmailSignatureApi(name: string, html: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/emails/signatures?name=${encodeURIComponent(name)}&html=${encodeURIComponent(html)}`);
}

export async function fetchEmailThreadApi(threadId: string): Promise<EmailThreadResponse> {
  return apiClient.get<EmailThreadResponse>(`/emails/threads/${threadId}`);
}

export async function bulkDeleteEmailsApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/emails/bulk-delete', { ids });
}

export async function syncImapInboxApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/emails/sync/imap');
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useInboxQuery(params?: { page?: number; limit?: number; folder?: string; search?: string }, options?: Omit<UseQueryOptions<EmailMessageItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<EmailMessageItem[]>({
    queryKey: ['emails', 'inbox', params],
    queryFn: () => fetchInboxApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useDraftsQuery(options?: Omit<UseQueryOptions<EmailMessageItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<EmailMessageItem[]>({
    queryKey: ['emails', 'drafts'],
    queryFn: fetchDraftsApi,
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useEmailTemplatesQuery(options?: Omit<UseQueryOptions<EmailTemplateItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<EmailTemplateItem[]>({
    queryKey: ['emails', 'templates'],
    queryFn: fetchEmailTemplatesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useEmailTrackingStatusQuery(emailId: string, options?: Omit<UseQueryOptions<EmailTrackingStatus>, 'queryKey' | 'queryFn'>) {
  return useQuery<EmailTrackingStatus>({
    queryKey: ['emails', 'tracking', emailId],
    queryFn: () => fetchEmailTrackingStatusApi(emailId),
    enabled: !!emailId,
    ...options,
  });
}

export function useEmailSignaturesQuery(options?: Omit<UseQueryOptions<EmailSignatureItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<EmailSignatureItem[]>({
    queryKey: ['emails', 'signatures'],
    queryFn: fetchEmailSignaturesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useEmailThreadQuery(threadId: string, options?: Omit<UseQueryOptions<EmailThreadResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<EmailThreadResponse>({
    queryKey: ['emails', 'threads', threadId],
    queryFn: () => fetchEmailThreadApi(threadId),
    enabled: !!threadId,
    ...options,
  });
}

export function useSendEmailMutation(options?: UseMutationOptions<EmailMessageItem, Error, EmailSendPayload>) {
  const queryClient = useQueryClient();
  return useMutation<EmailMessageItem, Error, EmailSendPayload>({
    mutationFn: sendEmailApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails', 'inbox'] });
    },
    ...options,
  });
}

export function useSaveDraftMutation(options?: UseMutationOptions<MessageResponse, Error, EmailSendPayload>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, EmailSendPayload>({
    mutationFn: saveDraftApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails', 'drafts'] });
    },
    ...options,
  });
}

export function useCreateEmailTemplateMutation(options?: UseMutationOptions<MessageResponse, Error, { name: string; subject: string; body: string; category?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { name: string; subject: string; body: string; category?: string }>({
    mutationFn: ({ name, subject, body, category }) => createEmailTemplateApi(name, subject, body, category),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails', 'templates'] });
    },
    ...options,
  });
}

export function useSendBulkCampaignMutation(options?: UseMutationOptions<{ campaign_id: string; queued_count: number; status: string }, Error, { template_id: string; lead_ids: string[] }>) {
  return useMutation({
    mutationFn: ({ template_id, lead_ids }) => sendBulkCampaignApi(template_id, lead_ids),
    ...options,
  });
}

export function useSaveEmailSignatureMutation(options?: UseMutationOptions<MessageResponse, Error, { name: string; html: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { name: string; html: string }>({
    mutationFn: ({ name, html }) => saveEmailSignatureApi(name, html),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails', 'signatures'] });
    },
    ...options,
  });
}

export function useBulkDeleteEmailsMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteEmailsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails', 'inbox'] });
    },
    ...options,
  });
}

export function useSyncImapInboxMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: syncImapInboxApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails', 'inbox'] });
    },
    ...options,
  });
}
