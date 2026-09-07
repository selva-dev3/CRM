import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ApiError, apiClient } from './client';
import { finalizeInvoiceApi, sendInvoiceEmailApi, useFinalizeInvoiceMutation } from './invoices';
import { fetchInvoicePaymentSummariesPageApi, recordInvoicePaymentApi, useRecordInvoicePaymentMutation } from './payments';
import { acceptPublicInvoiceApi, publicInvoiceKeys, useAcceptPublicInvoiceMutation, usePublicInvoiceQuery, viewPublicInvoiceApi } from './public-invoices';
import { manualPaymentSchema } from '@/lib/types/manual-payment';
vi.mock('./client', async (importOriginal) => ({ ...await importOriginal<typeof import('./client')>(), apiClient: { post: vi.fn(), getWithMetadata: vi.fn() } }));

const payment = { amount: '12.50', payment_type: 'UPI' as const, payment_date: '2026-09-06', notes: 'Receipt' };
describe('manual invoice API contract', () => {
  beforeEach(() => vi.clearAllMocks());
  it('preserves raw token, decimal string, recipient route, and retry key', async () => {
    await finalizeInvoiceApi('invoice-1');
    expect(apiClient.post).toHaveBeenLastCalledWith('/invoices/invoice-1/finalize');
    const operation = { invoiceId: 'invoice-1', payment, idempotencyKey: 'same-key' };
    await recordInvoicePaymentApi(operation); await recordInvoicePaymentApi(operation);
    expect(apiClient.post).toHaveBeenLastCalledWith('/invoices/invoice-1/payments', payment, { headers: { 'Idempotency-Key': 'same-key' } });
    await sendInvoiceEmailApi('invoice-1', 'a+b@example.com');
    expect(apiClient.post).toHaveBeenLastCalledWith('/invoices/invoice-1/send?recipient_email=a%2Bb%40example.com');
    const token = 'a'.repeat(64);
    await viewPublicInvoiceApi(token); await acceptPublicInvoiceApi(token);
    expect(apiClient.post).toHaveBeenCalledWith('/public/invoices/view', { token }, { credentials: 'omit' });
    expect(apiClient.post).toHaveBeenLastCalledWith('/public/invoices/accept', { token }, { credentials: 'omit' });
  });
  it('loads paginated invoice payment summaries with backend status filters', async () => {
    vi.mocked(apiClient.getWithMetadata).mockResolvedValue({
      data: [], headers: new Headers({ 'X-Total-Count': '0' }), status: 200,
    });
    await fetchInvoicePaymentSummariesPageApi({ page: 2, limit: 20, status: 'Partially Paid', search: 'INV-7' });
    expect(apiClient.getWithMetadata).toHaveBeenCalledWith('/payments/invoice-summaries?page=2&limit=20&status=Partially+Paid&search=INV-7');
  });
  it('validates controlled types, real dates, and positive decimal syntax', () => {
    expect(manualPaymentSchema.safeParse(payment).success).toBe(true);
    for (const invalid of [{ payment_type: 'Legacy' }, { amount: '1e2' }, { amount: '-1' }, { payment_date: '2026-02-30' }]) {
      expect(manualPaymentSchema.safeParse({ ...payment, ...invalid }).success).toBe(false);
    }
  });
  it('enforces the backend amount and notes boundaries', () => {
    for (const amount of ['0.01', '1', '1.2', '999999999999.99']) {
      expect(manualPaymentSchema.safeParse({ ...payment, amount, notes: 'x'.repeat(2000) }).success).toBe(true);
    }
    for (const amount of ['1.001', '999999999999.999', '1000000000000', '0', '1.']) {
      expect(manualPaymentSchema.safeParse({ ...payment, amount }).success).toBe(false);
    }
    expect(manualPaymentSchema.safeParse({ ...payment, notes: 'x'.repeat(2001) }).success).toBe(false);
  });
  it('uses the current UTC date for the future-date boundary', () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    try {
      vi.setSystemTime(new Date('2026-09-06T23:59:59Z'));
      expect(manualPaymentSchema.safeParse({ ...payment, payment_date: '2026-09-06' }).success).toBe(true);
      expect(manualPaymentSchema.safeParse({ ...payment, payment_date: '2026-09-07' }).success).toBe(false);
      vi.setSystemTime(new Date('2026-09-07T00:00:00Z'));
      expect(manualPaymentSchema.safeParse({ ...payment, payment_date: '2026-09-07' }).success).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
  it('refreshes invoice, payment, report and public view caches after mutations', async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => ({ payment: useRecordInvoicePaymentMutation(), finalize: useFinalizeInvoiceMutation(), accept: useAcceptPublicInvoiceMutation('token') }), { wrapper });
    await act(async () => { await result.current.payment.mutateAsync({ invoiceId: 'invoice-1', payment, idempotencyKey: 'key' }); await result.current.finalize.mutateAsync('invoice-1'); await result.current.accept.mutateAsync(); });
    for (const key of [['payments'], ['invoices'], ['reports'], publicInvoiceKeys.view('token')]) expect(invalidate).toHaveBeenCalledWith({ queryKey: key });
    client.clear();
  });
  it('gates malformed public tokens and loads valid links', async () => {
    const client = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    vi.mocked(apiClient.post).mockResolvedValue({ invoice_number: 'INV-1' });
    const { result, rerender } = renderHook(({ token }) => usePublicInvoiceQuery(token), { initialProps: { token: '' }, wrapper });
    expect(apiClient.post).not.toHaveBeenCalled();
    rerender({ token: 'a'.repeat(64) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    client.clear();
  });
  it('refreshes invoice balances after a rejected concurrent payment', async () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const conflict = new ApiError('Balance changed', 'http', 409, 'PAYMENT_EXCEEDS_BALANCE');
    vi.mocked(apiClient.post).mockRejectedValueOnce(conflict);
    const { result } = renderHook(() => useRecordInvoicePaymentMutation(), { wrapper });
    await act(async () => {
      await expect(result.current.mutateAsync({ invoiceId: 'invoice-1', payment, idempotencyKey: 'key' })).rejects.toBe(conflict);
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['invoices'] });
    client.clear();
  });
});
