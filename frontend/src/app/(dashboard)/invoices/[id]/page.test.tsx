import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Page from './page';

const mocks = vi.hoisted(() => ({ status: 'Finalized', send: vi.fn() }));
vi.mock('next/navigation', () => ({ useParams: () => ({ id: 'invoice-1' }), useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/hooks/use-has-permission', () => ({ useHasPermission: () => ({ hasPermission: () => true }) }));
vi.mock('@/components/features/invoices/InvoiceWorkflowActions', () => ({ InvoiceWorkflowActions: () => null }));
vi.mock('@/lib/api/invoices', () => ({
  useInvoiceQuery: () => ({ data: { id: 'invoice-1', invoice_number: 'INV-1', status: mocks.status, amount: '108', currency: 'INR', delivery_status: 'Pending', payment_status: 'Pending', billing_snapshot: { email: 'client@example.com' }, items: [{ id: '1', product_name: 'Consulting', quantity: 1, unit_price: '100', total: '108', discount_percent: 10, tax_percent: 20 }] } }),
  useInvoicePdfQuery: () => ({}), useSendInvoiceEmailMutation: () => ({ mutateAsync: mocks.send }),
  useSendPaymentReminderMutation: () => ({}), useDeleteInvoiceMutation: () => ({}),
}));
vi.mock('@/lib/api/payments', () => ({
  usePaymentsPageQuery: () => ({ data: { items: [], total: 0 } }),
}));
beforeEach(() => { vi.clearAllMocks(); mocks.status = 'Finalized'; mocks.send.mockResolvedValue({ status: 'Pending' }); });
it('uses server totals and invoice currency and shows acceptance wait', () => {
  render(<Page />);
  expect(screen.getByText('Waiting for customer acceptance.')).toBeInTheDocument();
  expect(screen.getAllByText('₹108.00').length).toBeGreaterThan(0);
  expect(screen.getByText('Consulting')).toBeInTheDocument();
  expect(screen.getByText('Tax %')).toBeInTheDocument();
});
it('prefills snapshot email and reports queued delivery', async () => {
  render(<Page />);
  fireEvent.click(screen.getByRole('button', { name: 'Send Invoice' }));
  expect(screen.getByDisplayValue('client@example.com')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Send Email' }));
  await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ id: 'invoice-1', recipient_email: 'client@example.com' }));
  expect(await screen.findByText('Invoice email queued for client@example.com.')).toBeInTheDocument();
});
it('hides Send Invoice on Draft', () => {
  mocks.status = 'Draft'; render(<Page />);
  expect(screen.queryByRole('button', { name: 'Send Invoice' })).not.toBeInTheDocument();
});
