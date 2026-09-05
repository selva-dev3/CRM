import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import DealDetailsPage from './page';

const push = vi.fn();
const updateDealMutateAsync = vi.fn();

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'deal-1' }),
  useRouter: () => ({ push }),
}));

vi.mock('@/lib/api/deals', () => ({
  useDealQuery: vi.fn(),
  useUpdateDealMutation: () => ({ mutateAsync: updateDealMutateAsync, isPending: false }),
  useDeleteDealMutation: () => ({ mutateAsync: vi.fn() }),
  useMarkDealWonMutation: () => ({ mutateAsync: vi.fn() }),
  useMarkDealLostMutation: () => ({ mutateAsync: vi.fn() }),
  getDealProductsApi: vi.fn().mockResolvedValue([]),
  addDealProductApi: vi.fn(),
  removeDealProductApi: vi.fn(),
  getDealTimelineApi: vi.fn().mockResolvedValue([]),
  getDealNotesApi: vi.fn().mockResolvedValue([]),
  addDealNoteApi: vi.fn(),
  getDealQuotesApi: vi.fn().mockResolvedValue([]),
  predictDealWinRateApi: vi.fn(),
  cloneDealApi: vi.fn(),
  getDealCommissionApi: vi.fn().mockResolvedValue(null),
}));

const convertMutate = vi.fn();
let dealInvoicesData: Array<Record<string, unknown>> = [];

vi.mock('@/lib/api/invoices', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useDealInvoicesQuery: () =>
      actual.useQuery({
        queryKey: ['invoices', 'deal', 'deal-1'],
        queryFn: async () => dealInvoicesData,
      }),
    useConvertDealToInvoiceMutation: () => ({ mutateAsync: convertMutate, isPending: false }),
  };
});

vi.mock('@/lib/api/users', () => ({
  useUsersQuery: () => ({ data: [] }),
}));

vi.mock('@/lib/api/products', () => ({
  useProductsQuery: () => ({ data: [] }),
}));

vi.mock('@/lib/api/custom-fields', () => ({
  useEntityCustomFieldsQuery: () => ({
    data: [
      {
        field_name: 'decision_maker',
        field_type: 'text',
        label: 'Decision Maker',
        options: [],
      },
    ],
    isLoading: false,
    isError: false,
  }),
}));

import { useDealQuery } from '@/lib/api/deals';

function setStoredUser(permissions: string[]): void {
  window.localStorage.setItem(
    'user',
    JSON.stringify({ role: 'member', email: 'member@company.com', permissions })
  );
}

function renderPage(): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <DealDetailsPage />
    </QueryClientProvider>
  );
}

const baseDeal = {
  id: 'deal-1',
  title: 'Acme Corp Deal',
  amount: 25000,
  stage: 'Qualification',
  probability: 20,
  custom_fields: { decision_maker: 'CTO' },
};

describe('DealDetailsPage invoice lifecycle UX', () => {
  beforeEach(() => {
    vi.mocked(useDealQuery).mockReturnValue({
      data: baseDeal,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
    dealInvoicesData = [];
    setStoredUser(['deals:read', 'deals:update', 'invoices:create']);
  });

  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('explains automatic quote creation before Closed Won', async () => {
    renderPage();

    expect(
      await screen.findByText('Closing the deal creates its quote automatically')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Create Invoice/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/View Invoice/i)).not.toBeInTheDocument();
  });

  it('explains automatic invoice creation after Closed Won', async () => {
    vi.mocked(useDealQuery).mockReturnValue({
      data: { ...baseDeal, stage: 'Closed Won', probability: 100 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
    renderPage();

    expect(
      await screen.findByText('Invoice is created after customer accepts the quote')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Create Invoice/i })).not.toBeInTheDocument();
  });

  it('hides Create Invoice when the user lacks invoices:create permission', async () => {
    setStoredUser(['deals:read']);
    vi.mocked(useDealQuery).mockReturnValue({
      data: { ...baseDeal, stage: 'Closed Won', probability: 100 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
    renderPage();

    await screen.findAllByText('Closed Won');
    expect(screen.queryByRole('button', { name: /Create Invoice/i })).not.toBeInTheDocument();
  });

  it('shows View Invoice with the reference once an invoice exists', async () => {
    dealInvoicesData = [
      { id: 'inv-1', invoice_number: 'INV-1001', status: 'Draft', amount: 25000 },
    ];
    vi.mocked(useDealQuery).mockReturnValue({
      data: { ...baseDeal, stage: 'Closed Won', probability: 100 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
    renderPage();

    const viewLink = await screen.findByText(/View Invoice/i);
    expect(viewLink).toBeInTheDocument();
    expect(screen.getByText('INV-1001')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Create Invoice/i })).not.toBeInTheDocument();
  });

  it('loads and submits custom fields from the edit modal', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: 'More' }));
    await user.click(await screen.findByRole('menuitem', { name: 'Edit deal' }));
    expect(screen.getByLabelText('Decision Maker')).toHaveValue('CTO');
    await user.clear(screen.getByLabelText('Decision Maker'));
    await user.type(screen.getByLabelText('Decision Maker'), 'CFO');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(updateDealMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'deal-1',
          data: expect.objectContaining({ custom_fields: { decision_maker: 'CFO' } }),
        }),
      );
    });
  });
});
