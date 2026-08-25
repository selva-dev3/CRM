import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface InvoiceLineItem {
  id: string;
  product_id: string;
  description?: string | null;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  tax_percent: number;
}

export interface InvoiceItem {
  id: string;
  invoice_number: string;
  deal_id?: string | null;
  company_id?: string | null;
  contact_id?: string | null;
  currency?: string;
  amount: number;
  subtotal?: number;
  discount_total?: number;
  tax_total?: number;
  paid_amount?: number;
  status: string;
  due_date?: string | null;
  notes?: string | null;
  sent_at?: string | null;
  stripe_checkout_url?: string | null;
  created_at?: string | null;
  items?: InvoiceLineItem[];
}

export interface InvoiceCreatePayload {
  deal_id: string;
  invoice_number?: string;
  amount?: number;
  status?: string;
  due_date?: string;
}

export interface RecurringInvoiceSchedule {
  id: string;
  customer_name: string;
  amount: number;
  interval: string;
  next_billing_date: string;
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

export async function fetchInvoicesApi(params?: { page?: number; limit?: number; status?: string; search?: string }): Promise<InvoiceItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.status) query.append('status', params.status);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/invoices${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<InvoiceItem[]>(endpoint);
}

export async function createInvoiceApi(payload: InvoiceCreatePayload): Promise<InvoiceItem> {
  return apiClient.post<InvoiceItem>('/invoices', payload);
}

export async function fetchOverdueInvoicesApi(): Promise<InvoiceItem[]> {
  return apiClient.get<InvoiceItem[]>('/invoices/overdue');
}

export async function fetchRecurringInvoicesApi(): Promise<RecurringInvoiceSchedule[]> {
  return apiClient.get<RecurringInvoiceSchedule[]>('/invoices/recurring');
}

export async function createRecurringInvoiceApi(customer_id: string, amount: number, interval: string = 'Monthly'): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/invoices/recurring?customer_id=${encodeURIComponent(customer_id)}&amount=${amount}&interval=${encodeURIComponent(interval)}`);
}

export async function exportInvoicesCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/invoices/export/csv');
}

export async function importInvoicesCsvApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/invoices/import/csv');
}

export async function bulkDeleteInvoicesApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/invoices/bulk-delete', { ids });
}

export async function bulkRemindInvoicesApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/invoices/bulk-remind', { ids });
}

export async function fetchInvoiceApi(invoiceId: string): Promise<InvoiceItem> {
  return apiClient.get<InvoiceItem>(`/invoices/${invoiceId}`);
}

export async function convertDealToInvoiceApi(dealId: string): Promise<InvoiceItem> {
  return apiClient.post<InvoiceItem>(`/deals/${dealId}/invoice`);
}

export async function fetchDealInvoicesApi(dealId: string): Promise<InvoiceItem[]> {
  try {
    const data = await apiClient.get<InvoiceItem[]>(`/deals/${dealId}/invoices`);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function updateInvoiceApi(invoiceId: string, payload: InvoiceCreatePayload): Promise<InvoiceItem> {
  return apiClient.put<InvoiceItem>(`/invoices/${invoiceId}`, payload);
}

export async function deleteInvoiceApi(invoiceId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/invoices/${invoiceId}`);
}

export async function sendInvoiceEmailApi(invoiceId: string, recipient_email: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/invoices/${invoiceId}/send?recipient_email=${encodeURIComponent(recipient_email)}`);
}

export async function createStripeCheckoutApi(invoiceId: string): Promise<{ checkout_url: string }> {
  return apiClient.post<{ checkout_url: string }>(`/invoices/${invoiceId}/stripe-checkout`);
}

export async function markInvoicePaidApi(invoiceId: string, payment_method: string = 'Bank Transfer'): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/invoices/${invoiceId}/mark-paid?payment_method=${encodeURIComponent(payment_method)}`);
}

export async function sendPaymentReminderApi(invoiceId: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/invoices/${invoiceId}/remind`);
}

export async function fetchInvoicePdfApi(invoiceId: string): Promise<{ pdf_url: string }> {
  return apiClient.get<{ pdf_url: string }>(`/invoices/${invoiceId}/pdf`);
}

export async function issueCreditMemoApi(invoiceId: string, amount: number, reason: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/invoices/${invoiceId}/credit-memo?amount=${amount}&reason=${encodeURIComponent(reason)}`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useInvoicesQuery(params?: { page?: number; limit?: number; status?: string; search?: string }, options?: Omit<UseQueryOptions<InvoiceItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<InvoiceItem[]>({
    queryKey: ['invoices', params],
    queryFn: () => fetchInvoicesApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useInvoiceQuery(invoiceId: string, options?: Omit<UseQueryOptions<InvoiceItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<InvoiceItem>({
    queryKey: ['invoices', invoiceId],
    queryFn: () => fetchInvoiceApi(invoiceId),
    enabled: !!invoiceId,
    ...options,
  });
}

export function useDealInvoicesQuery(dealId: string) {
  return useQuery<InvoiceItem[]>({
    queryKey: ['invoices', 'deal', dealId],
    queryFn: () => fetchDealInvoicesApi(dealId),
    enabled: !!dealId,
    staleTime: 1000 * 60 * 2,
  });
}

export function useConvertDealToInvoiceMutation(options?: UseMutationOptions<InvoiceItem, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<InvoiceItem, Error, string>({
    mutationFn: (dealId) => convertDealToInvoiceApi(dealId),
    onSuccess: (invoice, dealId) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoices', 'deal', dealId] });
    },
    ...options,
  });
}

export function useOverdueInvoicesQuery(options?: Omit<UseQueryOptions<InvoiceItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<InvoiceItem[]>({
    queryKey: ['invoices', 'overdue'],
    queryFn: fetchOverdueInvoicesApi,
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useRecurringInvoicesQuery(options?: Omit<UseQueryOptions<RecurringInvoiceSchedule[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<RecurringInvoiceSchedule[]>({
    queryKey: ['invoices', 'recurring'],
    queryFn: fetchRecurringInvoicesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useInvoicePdfQuery(invoiceId: string, options?: Omit<UseQueryOptions<{ pdf_url: string }>, 'queryKey' | 'queryFn'>) {
  return useQuery<{ pdf_url: string }>({
    queryKey: ['invoices', invoiceId, 'pdf'],
    queryFn: () => fetchInvoicePdfApi(invoiceId),
    enabled: !!invoiceId,
    ...options,
  });
}

export function useCreateInvoiceMutation(options?: UseMutationOptions<InvoiceItem, Error, InvoiceCreatePayload>) {
  const queryClient = useQueryClient();
  return useMutation<InvoiceItem, Error, InvoiceCreatePayload>({
    mutationFn: createInvoiceApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    ...options,
  });
}

export function useUpdateInvoiceMutation(options?: UseMutationOptions<InvoiceItem, Error, { id: string; payload: InvoiceCreatePayload }>) {
  const queryClient = useQueryClient();
  return useMutation<InvoiceItem, Error, { id: string; payload: InvoiceCreatePayload }>({
    mutationFn: ({ id, payload }) => updateInvoiceApi(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoices', variables.id] });
    },
    ...options,
  });
}

export function useDeleteInvoiceMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteInvoiceApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    ...options,
  });
}

export function useBulkDeleteInvoicesMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteInvoicesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    ...options,
  });
}

export function useBulkRemindInvoicesMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkRemindInvoicesApi,
    ...options,
  });
}

export function useSendInvoiceEmailMutation(options?: UseMutationOptions<MessageResponse, Error, { id: string; recipient_email: string }>) {
  return useMutation<MessageResponse, Error, { id: string; recipient_email: string }>({
    mutationFn: ({ id, recipient_email }) => sendInvoiceEmailApi(id, recipient_email),
    ...options,
  });
}

export function useCreateStripeCheckoutMutation(options?: UseMutationOptions<{ checkout_url: string }, Error, string>) {
  return useMutation<{ checkout_url: string }, Error, string>({
    mutationFn: createStripeCheckoutApi,
    ...options,
  });
}

export function useMarkInvoicePaidMutation(options?: UseMutationOptions<MessageResponse, Error, { id: string; payment_method?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { id: string; payment_method?: string }>({
    mutationFn: ({ id, payment_method }) => markInvoicePaidApi(id, payment_method),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoices', variables.id] });
    },
    ...options,
  });
}

export function useSendPaymentReminderMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  return useMutation<MessageResponse, Error, string>({
    mutationFn: sendPaymentReminderApi,
    ...options,
  });
}

export function useIssueCreditMemoMutation(options?: UseMutationOptions<MessageResponse, Error, { id: string; amount: number; reason: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { id: string; amount: number; reason: string }>({
    mutationFn: ({ id, amount, reason }) => issueCreditMemoApi(id, amount, reason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoices', variables.id] });
    },
    ...options,
  });
}

export function useCreateRecurringInvoiceMutation(options?: UseMutationOptions<MessageResponse, Error, { customer_id: string; amount: number; interval?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { customer_id: string; amount: number; interval?: string }>({
    mutationFn: ({ customer_id, amount, interval }) => createRecurringInvoiceApi(customer_id, amount, interval),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices', 'recurring'] });
    },
    ...options,
  });
}

export function useImportInvoicesCsvMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: importInvoicesCsvApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    ...options,
  });
}
