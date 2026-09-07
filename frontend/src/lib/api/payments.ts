import { useQuery, useMutation, useQueryClient, type UseQueryOptions } from '@tanstack/react-query';
import type { ManualPaymentDto } from '@/lib/types/manual-payment';

import { ApiError, apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

export interface PaymentItem {
  id: string;
  invoice_id: string;
  invoice_number: string;
  payment_number: string;
  company_name?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  amount: number | string;
  currency: string;
  payment_type: ManualPaymentDto['payment_type'] | 'Legacy';
  payment_date: string;
  notes?: string | null;
  status: string;
  paid_at?: string | null;
  created_at?: string | null;
  invoice_total?: number | string;
  invoice_paid_amount?: number | string;
  invoice_outstanding_amount?: number | string;
  invoice_payment_status?: string;
  customer?: { id: string | null; name: string | null } | null;
}

export type EligiblePaymentInvoice = {
  id: string;
  invoice_number: string;
  customer_name?: string | null;
  contact_name?: string | null;
  amount: number | string;
  paid_amount: number | string;
  outstanding_amount: number | string;
  currency: string;
  payment_status: string;
};

export interface InvoicePaymentSummary {
  id: string;
  invoice_id: string;
  invoice_number: string;
  company_name?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  amount: number | string;
  paid_amount: number | string;
  outstanding_amount: number | string;
  currency: string;
  payment_status: 'Pending' | 'Partially Paid' | 'Paid';
  latest_payment_id?: string | null;
  payment_number?: string | null;
  payment_type?: string | null;
  latest_payment_amount?: number | string | null;
  payment_date?: string | null;
  notes?: string | null;
}

export interface PaymentQueryParams {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
  invoice_id?: string;
}

export const paymentKeys = { all: ['payments'] as const, list: (params?: PaymentQueryParams) => ['payments', params] as const, summaryList: (params?: PaymentQueryParams) => ['payments', 'invoice-summaries', params] as const, detail: (id: string) => ['payments', id] as const, eligibleInvoices: () => ['payments', 'eligible-invoices'] as const };

export function recordInvoicePaymentApi({ invoiceId, payment, idempotencyKey }: { invoiceId: string; payment: ManualPaymentDto; idempotencyKey: string }): Promise<PaymentItem> {
  return apiClient.post(`/invoices/${invoiceId}/payments`, payment, { headers: { 'Idempotency-Key': idempotencyKey } });
}

export function useRecordInvoicePaymentMutation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: recordInvoicePaymentApi,
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        await client.invalidateQueries({ queryKey: ['invoices'] });
      }
    },
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: paymentKeys.all }),
        client.invalidateQueries({ queryKey: paymentKeys.eligibleInvoices() }),
        client.invalidateQueries({ queryKey: ['invoices'] }),
        client.invalidateQueries({ queryKey: ['reports'] }),
      ]);
    },
  });
}

export async function fetchPaymentsApi(params?: PaymentQueryParams): Promise<PaymentItem[]> {
  return (await fetchPaymentsPageApi(params)).items;
}

export async function fetchPaymentsPageApi(
  params?: PaymentQueryParams,
): Promise<PaginatedResult<PaymentItem>> {
  const query = new URLSearchParams();
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.status) query.set('status', params.status);
  if (params?.search) query.set('search', params.search);
  if (params?.invoice_id) query.set('invoice_id', params.invoice_id);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return fetchPaginated<PaymentItem>(`/payments${suffix}`);
}

export async function fetchPaymentApi(paymentId: string): Promise<PaymentItem> {
  return apiClient.get<PaymentItem>(`/payments/${paymentId}`);
}

export async function fetchInvoicePaymentSummariesPageApi(
  params?: PaymentQueryParams,
): Promise<PaginatedResult<InvoicePaymentSummary>> {
  const query = new URLSearchParams();
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.status) query.set('status', params.status);
  if (params?.search) query.set('search', params.search);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return fetchPaginated<InvoicePaymentSummary>(`/payments/invoice-summaries${suffix}`);
}

export async function fetchEligiblePaymentInvoicesApi(): Promise<EligiblePaymentInvoice[]> {
  return apiClient.get<EligiblePaymentInvoice[]>('/payments/eligible-invoices');
}

export function usePaymentsQuery(
  params?: PaymentQueryParams,
  options?: Omit<UseQueryOptions<PaymentItem[], Error>, 'queryKey' | 'queryFn'>,
) {
  return useQuery<PaymentItem[], Error>({
    queryKey: paymentKeys.list(params),
    queryFn: () => fetchPaymentsApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function usePaymentsPageQuery(
  params?: PaymentQueryParams,
  options?: Omit<UseQueryOptions<PaginatedResult<PaymentItem>, Error>, 'queryKey' | 'queryFn'>,
) {
  return useQuery<PaginatedResult<PaymentItem>, Error>({
    queryKey: [...paymentKeys.list(params), 'paginated'],
    queryFn: () => fetchPaymentsPageApi(params),
    staleTime: 1000 * 60 * 2,
    placeholderData: (previousData) => previousData,
    ...options,
  });
}

export function useInvoicePaymentSummariesPageQuery(
  params?: PaymentQueryParams,
  options?: Omit<UseQueryOptions<PaginatedResult<InvoicePaymentSummary>, Error>, 'queryKey' | 'queryFn'>,
) {
  return useQuery<PaginatedResult<InvoicePaymentSummary>, Error>({
    queryKey: paymentKeys.summaryList(params),
    queryFn: () => fetchInvoicePaymentSummariesPageApi(params),
    staleTime: 1000 * 60 * 2,
    placeholderData: (previousData) => previousData,
    ...options,
  });
}

export function usePaymentQuery(paymentId: string, options?: Omit<UseQueryOptions<PaymentItem, Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<PaymentItem, Error>({ queryKey: paymentKeys.detail(paymentId), queryFn: () => fetchPaymentApi(paymentId), enabled: Boolean(paymentId), ...options });
}

export function useEligiblePaymentInvoicesQuery(options?: Omit<UseQueryOptions<EligiblePaymentInvoice[], Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<EligiblePaymentInvoice[], Error>({ queryKey: paymentKeys.eligibleInvoices(), queryFn: fetchEligiblePaymentInvoicesApi, staleTime: 30_000, ...options });
}
