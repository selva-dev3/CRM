import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CustomerQuotePage from './page';

const api = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api/quotes', () => ({ publicQuoteApi: api }));

const sentQuote = { id: 'quote-test', quote_number: 'QUO-2026-000012', status: 'Sent', total_amount: 200, currency: 'INR', expires_at: '2026-06-10T00:00:00Z', contact_name: 'Selvakumar', company_name: 'New Company', contact_email: 'selvakumar@example.com', items: [{ product_name: 'Support service', quantity: 2, unit_price: 100, subtotal: 200, discount_total: 0, tax_total: 0, total: 200 }] };

afterEach(() => { sessionStorage.clear(); window.history.replaceState(null, '', '/'); api.mockReset(); });

describe('customer quote workflow', () => {
  it('does not request private data without a secure link', async () => {
    render(<CustomerQuotePage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('secure link');
    expect(api).not.toHaveBeenCalled();
  });

  it('shows only quote review and decision actions', async () => {
    window.history.replaceState(null, '', '/public/quote#test-token');
    api.mockResolvedValueOnce(sentQuote);
    render(<CustomerQuotePage />);
    expect(await screen.findByText('QUO-2026-000012')).toBeInTheDocument();
    expect(screen.getByText('Awaiting your approval')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Accept quote' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject quote' })).toBeInTheDocument();
    expect(screen.queryByText(/invoice|stripe|payment|checkout/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /refresh/i })).not.toBeInTheDocument();
  });

  it('confirms and accepts without exposing invoice or payment UI', async () => {
    window.history.replaceState(null, '', '/public/quote#accept-token');
    api.mockResolvedValueOnce(sentQuote).mockResolvedValueOnce({ quote_id: sentQuote.id, status: 'Accepted' });
    render(<CustomerQuotePage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Accept quote' }));
    expect(screen.getByRole('alertdialog')).toHaveTextContent('Accept this quote?');
    await userEvent.click(screen.getByRole('alertdialog').querySelector('button:last-child')!);
    expect(await screen.findByRole('heading', { name: 'Quote accepted' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Accept quote' })).not.toBeInTheDocument();
    expect(screen.queryByText(/invoice|stripe|payment|checkout/i)).not.toBeInTheDocument();
    expect(api).toHaveBeenLastCalledWith('accept', 'accept-token', '');
  });

  it('confirms rejection and sends the optional reason', async () => {
    window.history.replaceState(null, '', '/public/quote#reject-token');
    api.mockResolvedValueOnce(sentQuote).mockResolvedValueOnce({ quote_id: sentQuote.id, status: 'Rejected' });
    render(<CustomerQuotePage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Reject quote' }));
    await userEvent.type(screen.getByLabelText('Rejection reason (optional)'), 'Please revise the scope');
    await userEvent.click(screen.getByRole('alertdialog').querySelector('button:last-child')!);
    expect(await screen.findByRole('heading', { name: 'Quote rejected' })).toBeInTheDocument();
    expect(api).toHaveBeenLastCalledWith('reject', 'reject-token', 'Please revise the scope');
  });

  it('renders an already accepted quote without actions', async () => {
    window.history.replaceState(null, '', '/public/quote#state-token');
    api.mockResolvedValueOnce({ ...sentQuote, status: 'Accepted' });
    render(<CustomerQuotePage />);
    expect(await screen.findByRole('heading', { name: 'Quote accepted' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /accept|reject/i })).not.toBeInTheDocument();
  });

  it('shows an expired state and does not offer acceptance', async () => {
    window.history.replaceState(null, '', '/public/quote#expired-token');
    api.mockRejectedValueOnce(new Error('Quote link has expired'));
    render(<CustomerQuotePage />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Quote expired' })).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /accept|reject/i })).not.toBeInTheDocument();
  });
});
