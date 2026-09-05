import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import QuotesPage from './page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/api/deals', () => ({
  useDealsQuery: () => ({
    data: [{ id: 'deal-1', title: 'Acme Renewal', amount: 25000, stage: 'Proposal' }],
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('@/lib/api/quotes', () => ({
  useQuotesQuery: () => ({ data: [], isLoading: false }),
  useCreateQuoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

describe('QuotesPage automatic creation flow', () => {
  afterEach(() => vi.clearAllMocks());

  it('does not expose manual quote creation', () => {
    renderPage();

    expect(screen.queryByRole('button', { name: 'Create Quote' })).not.toBeInTheDocument();
    expect(
      screen.getByText(
        'Quotes are created from won deals; customer acceptance creates invoices automatically.'
      )
    ).toBeInTheDocument();
  });
});
