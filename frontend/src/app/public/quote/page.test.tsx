import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CustomerQuotePage from './page';

const api = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api/quotes', () => ({ publicQuoteApi: api }));

const sentQuote = { id: 'quote-test', quote_number: 'QUOTE-TEST', status: 'Sent',
  total_amount: 200, currency: 'INR', items: [
    { product_name: 'Support service', quantity: 2, unit_price: 100, total: 200 },
  ] };

afterEach(() => {
  sessionStorage.clear();
  window.history.replaceState(null, '', '/');
  api.mockReset();
});

describe('customer quote workflow', () => {
  it('does not request private data without a capability link', async () => {
    render(<CustomerQuotePage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Open the secure link');
    expect(api).not.toHaveBeenCalled();
  });

  it('accepts once and displays the invoice returned by the backend', async () => {
    window.history.replaceState(null, '', '/public/quote#test-customer-capability');
    api.mockResolvedValueOnce(sentQuote).mockResolvedValueOnce({ status: 'Accepted' })
      .mockResolvedValueOnce({ ...sentQuote, status: 'Accepted', invoice_id: 'invoice-test',
        invoice_number: 'INV-TEST', invoice_status: 'Pending' });
    render(<CustomerQuotePage />);
    const accept = await screen.findByRole('button', { name: 'Accept quote' });
    await userEvent.click(accept);
    expect(await screen.findByText('Invoice INV-TEST')).toBeInTheDocument();
    expect(screen.getByText('Payment status: Pending')).toBeInTheDocument();
    expect(api.mock.calls.filter(([action]) => action === 'accept')).toHaveLength(1);
    expect(window.location.hash).toBe('');
    expect(screen.queryByRole('button', { name: 'Accept quote' })).not.toBeInTheDocument();
  });

  it('shows an expired link error without acceptance or checkout actions', async () => {
    window.history.replaceState(null, '', '/public/quote#expired-capability');
    api.mockRejectedValueOnce(new Error('Quote link has expired'));
    render(<CustomerQuotePage />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('expired'));
    expect(screen.queryByRole('button', { name: 'Accept quote' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Pay securely/ })).not.toBeInTheDocument();
  });

  it('keeps payment pending until a refreshed backend response says Paid', async () => {
    sessionStorage.setItem('customer-quote-token', 'test-customer-capability');
    const invoice = { ...sentQuote, status: 'Accepted', invoice_id: 'invoice-test', invoice_number: 'INV-TEST' };
    api.mockResolvedValueOnce({ ...invoice, invoice_status: 'Pending' })
      .mockResolvedValueOnce({ ...invoice, invoice_status: 'Paid' });
    render(<CustomerQuotePage />);
    expect(await screen.findByText('Payment status: Pending')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    expect(await screen.findByText('Payment status: Paid')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Pay securely/ })).not.toBeInTheDocument();
  });
});
