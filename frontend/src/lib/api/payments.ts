import { useQuery, type UseQueryOptions } from '@tanstack/react-query';

import { apiClient } from '@/lib/api/client';

export interface PaymentItem {
  id: string;
  invoice_id: string;
  invoice_number: string;
  company_name?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  amount: number;
  currency: string;
  payment_method?: string | null;
  status: string;
  provider: string;
  provider_payment_id: string;
  checkout_session_id: string;
  paid_at: string;
  created_at?: string | null;
}

export interface PaymentQueryParams {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
  invoice_id?: string;
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
    queryKey: ['payments', params],
    queryFn: () => fetchPaymentsApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}
