import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { PublicInvoiceDto } from '@/lib/types/public-invoice';

export const publicInvoiceKeys = { view: (token: string) => ['public-invoice', token] as const };
export function viewPublicInvoiceApi(token: string): Promise<PublicInvoiceDto> {
  return apiClient.post('/public/invoices/view', { token }, { credentials: 'omit' });
}
export function acceptPublicInvoiceApi(token: string): Promise<unknown> {
  return apiClient.post('/public/invoices/accept', { token }, { credentials: 'omit' });
}
export function usePublicInvoiceQuery(token: string) {
  return useQuery({ queryKey: publicInvoiceKeys.view(token), queryFn: () => viewPublicInvoiceApi(token), enabled: /^[a-f0-9]{64}$/i.test(token), retry: false });
}
export function useAcceptPublicInvoiceMutation(token: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: () => acceptPublicInvoiceApi(token), onSuccess: () => client.invalidateQueries({ queryKey: publicInvoiceKeys.view(token) }) });
}
