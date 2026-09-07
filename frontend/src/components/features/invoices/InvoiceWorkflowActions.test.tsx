import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { InvoiceWorkflowActions } from './InvoiceWorkflowActions';
import { ApiError } from '@/lib/api/client';
import type { InvoiceItem } from '@/lib/api/invoices';

const mocks = vi.hoisted(() => ({ record: vi.fn(), finalize: vi.fn(), submitReview: vi.fn(), returnDraft: vi.fn(), permission: true }));
vi.mock('@/lib/api/payments', () => ({ useRecordInvoicePaymentMutation: () => ({ mutateAsync: mocks.record, isPending: false }) }));
vi.mock('@/lib/api/invoices', () => ({
  useFinalizeInvoiceMutation: () => ({ mutateAsync: mocks.finalize, isPending: false }),
  useSubmitInvoiceForReviewMutation: () => ({ mutateAsync: mocks.submitReview, isPending: false }),
  useReturnInvoiceToDraftMutation: () => ({ mutateAsync: mocks.returnDraft, isPending: false }),
}));
vi.mock('@/providers/auth-provider', () => ({ useOptionalAuth: () => ({ user: { id: 'user-1' } }) }));
vi.mock('@/hooks/use-has-permission', () => ({ useHasPermission: () => ({ hasPermission: () => mocks.permission }) }));

const invoice: InvoiceItem = { id: 'invoice-1', invoice_number: 'INV-1', amount: 100, status: 'Accepted', payment_status: 'Pending', outstanding_amount: '100.00', finalized_at: '2026-09-01', accepted_at: '2026-09-02', currency: 'INR' };
function fill(amount = '12.50') {
  fireEvent.change(screen.getByLabelText('Amount'), { target: { value: amount } });
  fireEvent.change(screen.getByLabelText('Payment date'), { target: { value: '2026-09-06' } });
  fireEvent.change(screen.getByLabelText('Payment type'), { target: { value: 'UPI' } });
}
function submit() { fireEvent.submit(screen.getByLabelText('Amount').closest('form') as HTMLFormElement); }

describe('invoice workflow', () => {
  beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); mocks.permission = true; mocks.record.mockResolvedValue({}); });
  it.each(['Draft', 'Finalized', 'Cancelled'])('does not allow payment for %s', (status) => {
    render(<InvoiceWorkflowActions invoice={{ ...invoice, status }} />);
    expect(screen.queryByRole('button', { name: 'Add Payment' })).not.toBeInTheDocument();
  });
  it.each([
    { payment_status: 'Paid' as const }, { outstanding_amount: '0' }, { accepted_at: null }, { finalized_at: null },
  ])('fails closed for unavailable payment eligibility: %o', (override) => {
    render(<InvoiceWorkflowActions invoice={{ ...invoice, ...override }} />);
    expect(screen.queryByRole('button', { name: 'Add Payment' })).not.toBeInTheDocument();
  });
  it('honors the payment permission', () => {
    mocks.permission = false;
    render(<InvoiceWorkflowActions invoice={invoice} />);
    expect(screen.queryByRole('button', { name: 'Add Payment' })).not.toBeInTheDocument();
  });
  it('submits a decimal string and controlled payment type and provides Cancel', async () => {
    render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' }));
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    expect(screen.getAllByRole('option').map(option => option.textContent)).toEqual(['Cash', 'Bank Transfer', 'Cheque', 'UPI', 'Card', 'Other']);
    fill(); submit();
    await waitFor(() => expect(mocks.record).toHaveBeenCalledWith({ invoiceId: 'invoice-1', idempotencyKey: expect.any(String), payment: { amount: '12.50', payment_type: 'UPI', payment_date: '2026-09-06', notes: '' } }));
    await waitFor(() => expect(sessionStorage.length).toBe(0));
  });
  it('blocks invalid and excessive amounts', async () => {
    render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' }));
    fill('0'); submit();
    expect(await screen.findByText('Amount must be greater than zero.')).toBeInTheDocument();
    fill('101'); submit();
    expect(await screen.findByText('Amount exceeds the outstanding balance.')).toBeInTheDocument();
    expect(mocks.record).not.toHaveBeenCalled();
  });
  it('maps server validation errors to fields and unlocks corrections', async () => {
    mocks.record.mockRejectedValueOnce(new ApiError('Invalid amount', 'http', 422, null, { 'body.amount': 'Balance changed' }));
    render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' })); fill(); submit();
    expect(await screen.findByText('Balance changed')).toBeInTheDocument();
    expect(screen.getByLabelText('Amount')).not.toBeDisabled();
  });
  it('allows correction after a definitive balance rejection', async () => {
    mocks.record.mockRejectedValueOnce(new ApiError('Balance changed', 'http', 409, 'PAYMENT_EXCEEDS_BALANCE'));
    render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' })); fill(); submit();
    expect(await screen.findByText('Balance changed')).toBeInTheDocument();
    expect(screen.getByLabelText('Amount')).not.toBeDisabled();
    expect(sessionStorage.length).toBe(0);
    fill('5.00'); submit();
    await waitFor(() => expect(mocks.record).toHaveBeenCalledTimes(2));
    expect(mocks.record.mock.calls[1][0].payment.amount).toBe('5.00');
    expect(mocks.record.mock.calls[1][0].idempotencyKey).not.toBe(mocks.record.mock.calls[0][0].idempotencyKey);
  });
  it('preserves evidence when the server reports an idempotency conflict', async () => {
    mocks.record.mockRejectedValueOnce(new ApiError('Existing operation differs', 'http', 409, 'PAYMENT_IDEMPOTENCY_CONFLICT'));
    render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' })); fill(); submit();
    expect(await screen.findByText('Existing operation differs')).toBeInTheDocument();
    expect(screen.getByLabelText('Amount')).toBeDisabled();
    expect(sessionStorage.length).toBe(1);
  });
  it('restores and retries the identical pending operation after a remount', async () => {
    mocks.record.mockRejectedValueOnce(new ApiError('Timed out', 'timeout'));
    const first = render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' })); fill(); submit();
    await screen.findByText('Timed out');
    const original = mocks.record.mock.calls[0][0];
    first.unmount();
    render(<InvoiceWorkflowActions invoice={invoice} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add Payment' }));
    expect(screen.getByLabelText('Amount')).toHaveValue('12.50');
    expect(screen.getByLabelText('Amount')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Retry same payment' }));
    await waitFor(() => expect(mocks.record).toHaveBeenLastCalledWith(original));
    await waitFor(() => expect(mocks.record).toHaveBeenCalledTimes(2));
  });
  it('submits a draft for review only after confirmation', async () => {
    render(<InvoiceWorkflowActions invoice={{ ...invoice, status: 'Draft' }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Submit for review' }));
    expect(mocks.submitReview).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole('button', { name: 'Submit for review' }).at(-1) as HTMLElement);
    await waitFor(() => expect(mocks.submitReview).toHaveBeenCalledWith('invoice-1'));
  });
  it('finalizes only an invoice in review after confirmation', async () => {
    render(<InvoiceWorkflowActions invoice={{ ...invoice, status: 'In Review' }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Approve & finalize' }));
    expect(mocks.finalize).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole('button', { name: 'Approve & finalize' }).at(-1) as HTMLElement);
    await waitFor(() => expect(mocks.finalize).toHaveBeenCalledWith('invoice-1'));
  });
});
