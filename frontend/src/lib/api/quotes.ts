import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface QuoteLineItem {
  name?: string;
  product_name?: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface QuoteItem {
  id: string;
  quote_number: string;
  client?: string;
  items?: QuoteLineItem[];
  total_amount: number;
  status: string;
  created_at: string;
  deal_id?: string | null;
  currency?: string | null;
  delivery_status?: string | null;
  recipient_email?: string | null;
  pdf_available?: boolean;
  expires_at?: string | null;
  invoice_id?: string | null;
  invoice_number?: string | null;
  invoice_status?: string | null;
}

export function publicQuoteApi(action: 'view', token: string): Promise<QuoteItem>;
export function publicQuoteApi(action: 'accept' | 'reject', token: string): Promise<{ status: string }>;
export function publicQuoteApi(action: 'checkout', token: string): Promise<{ checkout_url: string }>;
export function publicQuoteApi(action: string, token: string): Promise<unknown> {
  return apiClient.post(`/public/quotes/${action}`, { token }, { credentials: 'omit' });
}

export function approveQuoteApi(quoteId: string): Promise<QuoteItem> {
  return apiClient.post(`/quotes/${quoteId}/approve`);
}

export interface QuoteCreatePayload {
  deal_id: string;
  quote_number?: string;
  items?: QuoteLineItem[];
  total_amount: number;
  status?: string;
}

export interface QuoteRevisionItem {
  id: string;
  quote_number: string;
  total_amount: number;
  version: string;
  created_at: string;
}

export interface BulkActionResponse {
  affected_count: number;
  message: string;
}

export interface MessageResponse {
  message: string;
  status: string;
}

export interface InvoiceConversionResponse {
  id: string;
  invoice_number: string;
  amount: number;
  status: string;
  due_date: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchQuotesApi(params?: { page?: number; limit?: number; status?: string; search?: string }): Promise<QuoteItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.status) query.append('status', params.status);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/quotes${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<QuoteItem[]>(endpoint);
}

export async function createQuoteApi(payload: QuoteCreatePayload): Promise<QuoteItem> {
  return apiClient.post<QuoteItem>('/quotes', payload);
}

export async function exportQuotesCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/quotes/export/csv');
}

export async function importQuotesCsvApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/quotes/import/csv');
}

export async function bulkDeleteQuotesApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/quotes/bulk-delete', { ids });
}

export async function fetchQuoteApi(quoteId: string): Promise<QuoteItem> {
  return apiClient.get<QuoteItem>(`/quotes/${quoteId}`);
}

export async function updateQuoteApi(quoteId: string, payload: QuoteCreatePayload): Promise<QuoteItem> {
  return apiClient.put<QuoteItem>(`/quotes/${quoteId}`, payload);
}

export async function deleteQuoteApi(quoteId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/quotes/${quoteId}`);
}

export async function sendQuoteEmailApi(quoteId: string, recipient_email: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/quotes/${quoteId}/send?recipient_email=${encodeURIComponent(recipient_email)}`);
}

export async function acceptQuoteApi(quoteId: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/quotes/${quoteId}/accept`);
}

export async function rejectQuoteApi(quoteId: string, reason?: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/quotes/${quoteId}/reject?reason=${encodeURIComponent(reason || 'Budget constraints')}`);
}

export async function fetchQuotePdfApi(quoteId: string): Promise<{ pdf_url: string }> {
  return apiClient.get<{ pdf_url: string }>(`/quotes/${quoteId}/pdf`);
}

export async function convertQuoteToInvoiceApi(quoteId: string): Promise<InvoiceConversionResponse> {
  return apiClient.post<InvoiceConversionResponse>(`/quotes/${quoteId}/convert-to-invoice`);
}

export async function createQuoteRevisionApi(quoteId: string): Promise<QuoteItem> {
  return apiClient.post<QuoteItem>(`/quotes/${quoteId}/revisions`);
}

export async function fetchQuoteRevisionsApi(quoteId: string): Promise<QuoteRevisionItem[]> {
  return apiClient.get<QuoteRevisionItem[]>(`/quotes/${quoteId}/revisions`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useQuotesQuery(params?: { page?: number; limit?: number; status?: string; search?: string }, options?: Omit<UseQueryOptions<QuoteItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<QuoteItem[]>({
    queryKey: ['quotes', params],
    queryFn: () => fetchQuotesApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useQuoteQuery(quoteId: string, options?: Omit<UseQueryOptions<QuoteItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<QuoteItem>({
    queryKey: ['quotes', quoteId],
    queryFn: () => fetchQuoteApi(quoteId),
    enabled: !!quoteId,
    ...options,
  });
}

export function useQuotePdfQuery(quoteId: string, options?: Omit<UseQueryOptions<{ pdf_url: string }>, 'queryKey' | 'queryFn'>) {
  return useQuery<{ pdf_url: string }>({
    queryKey: ['quotes', quoteId, 'pdf'],
    queryFn: () => fetchQuotePdfApi(quoteId),
    enabled: !!quoteId,
    ...options,
  });
}

export function useQuoteRevisionsQuery(quoteId: string, options?: Omit<UseQueryOptions<QuoteRevisionItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<QuoteRevisionItem[]>({
    queryKey: ['quotes', quoteId, 'revisions'],
    queryFn: () => fetchQuoteRevisionsApi(quoteId),
    enabled: !!quoteId,
    ...options,
  });
}

export function useCreateQuoteMutation(options?: UseMutationOptions<QuoteItem, Error, QuoteCreatePayload>) {
  const queryClient = useQueryClient();
  return useMutation<QuoteItem, Error, QuoteCreatePayload>({
    mutationFn: createQuoteApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
    },
    ...options,
  });
}

export function useUpdateQuoteMutation(options?: UseMutationOptions<QuoteItem, Error, { id: string; payload: QuoteCreatePayload }>) {
  const queryClient = useQueryClient();
  return useMutation<QuoteItem, Error, { id: string; payload: QuoteCreatePayload }>({
    mutationFn: ({ id, payload }) => updateQuoteApi(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quotes', variables.id] });
    },
    ...options,
  });
}

export function useDeleteQuoteMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteQuoteApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
    },
    ...options,
  });
}

export function useBulkDeleteQuotesMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteQuotesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
    },
    ...options,
  });
}

export function useSendQuoteEmailMutation(options?: UseMutationOptions<MessageResponse, Error, { id: string; recipient_email: string }>) {
  return useMutation<MessageResponse, Error, { id: string; recipient_email: string }>({
    mutationFn: ({ id, recipient_email }) => sendQuoteEmailApi(id, recipient_email),
    ...options,
  });
}

export function useAcceptQuoteMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: acceptQuoteApi,
    onSuccess: (_, quoteId) => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quotes', quoteId] });
    },
    ...options,
  });
}

export function useRejectQuoteMutation(options?: UseMutationOptions<MessageResponse, Error, { id: string; reason?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { id: string; reason?: string }>({
    mutationFn: ({ id, reason }) => rejectQuoteApi(id, reason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quotes', variables.id] });
    },
    ...options,
  });
}

export function useConvertQuoteToInvoiceMutation(options?: UseMutationOptions<InvoiceConversionResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<InvoiceConversionResponse, Error, string>({
    mutationFn: convertQuoteToInvoiceApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    ...options,
  });
}

export function useCreateQuoteRevisionMutation(options?: UseMutationOptions<QuoteItem, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<QuoteItem, Error, string>({
    mutationFn: createQuoteRevisionApi,
    onSuccess: (_, quoteId) => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
      queryClient.invalidateQueries({ queryKey: ['quotes', quoteId, 'revisions'] });
    },
    ...options,
  });
}

export function useImportQuotesCsvMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: importQuotesCsvApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotes'] });
    },
    ...options,
  });
}
