import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PublicInvoiceView } from './PublicInvoiceView';
import { apiClient } from '@/lib/api/client';

vi.mock('@/lib/api/client', () => ({ apiClient: { post: vi.fn() } }));
const invoice = { invoice_number: 'INV-1', status: 'Finalized', payment_status: 'Pending', currency: 'INR', amount: '108.00', subtotal: '100.00', discount_total: '10.00', tax_total: '18.00', due_date: '2026-09-06', billing_snapshot: { email: 'client@example.com' }, items: [{ id: 'line-1', product_name: 'Consulting', quantity: 1, unit_price: '100.00', discount_percent: '10.00', tax_percent: '20.00', total: '108.00' }] };
function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PublicInvoiceView /></QueryClientProvider>);
}
beforeEach(() => { vi.clearAllMocks(); window.location.hash = 'a'.repeat(64); vi.mocked(apiClient.post).mockResolvedValue(invoice); });
it('renders decimal strings, currency, rates, server totals and approval status', async () => {
  mount();
  expect(await screen.findByText('Invoice INV-1')).toBeInTheDocument();
  expect(screen.getByText('Status: Awaiting your approval')).toBeInTheDocument();
  expect(screen.getByText('Discount %')).toBeInTheDocument();
  expect(screen.getByText('Tax %')).toBeInTheDocument();
  expect(screen.getAllByText('₹108.00').length).toBeGreaterThan(0);
  expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  expect(screen.queryByText('2026-09-06')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Payment|Checkout/i })).not.toBeInTheDocument();
  expect(apiClient.post).toHaveBeenCalledWith('/public/invoices/view', { token: 'a'.repeat(64) }, { credentials: 'omit' });
});
it('accepts with the raw fragment token and refreshes authoritative status', async () => {
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Accept invoice' }));
  vi.mocked(apiClient.post).mockResolvedValue({ ...invoice, status: 'Accepted', accepted_at: '2026-09-06T10:00:00Z' });
  fireEvent.click(screen.getByRole('button', { name: 'Confirm acceptance' }));
  await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/public/invoices/accept', { token: 'a'.repeat(64) }, { credentials: 'omit' }));
  expect(await screen.findByText(/Invoice accepted. Contact/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Accept invoice' })).not.toBeInTheDocument();
});
it.each(['Accepted', 'Cancelled', 'Draft'])('does not offer acceptance for %s', async (status) => {
  vi.mocked(apiClient.post).mockResolvedValue({ ...invoice, status });
  mount();
  await screen.findByText('Invoice INV-1');
  expect(screen.queryByRole('button', { name: 'Accept invoice' })).not.toBeInTheDocument();
});
it('rejects malformed tokens without calling the API', async () => {
  window.location.hash = 'invalid'; mount();
  expect(await screen.findByRole('alert')).toHaveTextContent('Open the complete secure invoice link');
  expect(apiClient.post).not.toHaveBeenCalled();
});
it('shows request failures and a retry action', async () => {
  vi.mocked(apiClient.post).mockRejectedValue(new Error('Invoice link expired'));
  mount();
  expect(await screen.findByText('Invoice link expired')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
});
