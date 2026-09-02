import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import QuotesPage from './page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const createQuote = vi.fn();

vi.mock('@/lib/api/deals', () => ({
  useDealsQuery: () => ({
    data: [{ id: 'deal-1', title: 'Acme Renewal', amount: 25000, stage: 'Proposal' }],
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/api/quotes', () => ({
  useQuotesQuery: () => ({ data: [], isLoading: false }),
  useCreateQuoteMutation: () => ({ mutateAsync: createQuote, isPending: false }),
  useUpdateQuoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteQuoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useBulkDeleteQuotesMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSendQuoteEmailMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAcceptQuoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRejectQuoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConvertQuoteToInvoiceMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useImportQuotesCsvMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  exportQuotesCsvApi: vi.fn(),
}));

function renderPage(): void {
  window.localStorage.setItem('user', JSON.stringify({ permissions: ['quotes:create', 'quotes:read'] }));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <QuotesPage />
    </QueryClientProvider>
  );
}

describe('QuotesPage creation flow', () => {
  afterEach(() => vi.clearAllMocks());

  it('requires and submits the selected deal id', async () => {
    const user = userEvent.setup();
    createQuote.mockResolvedValue({ id: 'quote-1' });
    renderPage();

    await user.click(screen.getByRole('button', { name: 'Create Quote' }));
    const dealSelect = screen.getByRole('combobox', { name: 'Deal *' });
    expect(dealSelect).toBeInTheDocument();

    await user.selectOptions(dealSelect, 'deal-1');
    const submitButtons = screen.getAllByRole('button', { name: /^Create Quote$/ });
    await user.click(submitButtons[submitButtons.length - 1]);

    expect(createQuote).toHaveBeenCalledWith(expect.objectContaining({ deal_id: 'deal-1' }));
  });
});
