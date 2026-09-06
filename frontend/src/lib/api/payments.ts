import { useQuery, useMutation, useQueryClient, type UseQueryOptions } from '@tanstack/react-query';
import type { ManualPaymentDto } from '@/lib/types/manual-payment';

import { ApiError, apiClient } from '@/lib/api/client';

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
}

export interface PaymentQueryParams {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
  invoice_id?: string;
}

export const paymentKeys = { all: ['payments'] as const, list: (params?: PaymentQueryParams) => ['payments', params] as const };

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
        client.invalidateQueries({ queryKey: ['invoices'] }),
        client.invalidateQueries({ queryKey: ['reports'] }),
      ]);
    },
  });
}

export async function fetchPaymentsApi(params?: PaymentQueryParams): Promise<PaymentItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.status) query.set('status', params.status);
  if (params?.search) query.set('search', params.search);
  if (params?.invoice_id) query.set('invoice_id', params.invoice_id);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return apiClient.get<PaymentItem[]>(`/payments${suffix}`);
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
