import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '@/lib/api/client';

const pushMock = vi.fn();
const documentsQueryMock = vi.fn();

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'company-1' }),
  useRouter: () => ({ push: pushMock }),
}));

const emptyQuery = {
  data: { items: [], total: 0 },
  isLoading: false,
  isError: false,
  error: null,
  refetch: vi.fn(),
};

vi.mock('@/lib/api/companies', () => ({
  useCompanyQuery: () => ({
    data: {
      id: 'company-1',
      name: 'Acme Corp',
      industry: 'Technology',
      website: 'https://acme.example',
      created_at: '2026-09-06T10:00:00Z',
      custom_fields: {},
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useCompanyContactsQuery: vi.fn((_id: string, enabled: boolean) => ({
    ...emptyQuery,
    data: enabled
      ? { items: [
          {
            id: 'contact-1',
            name: 'Jane Buyer',
            email: 'jane@example.test',
            position: 'CTO',
          },
        ], total: 1 }
      : undefined,
  })),
  useCompanyDealsQuery: vi.fn(() => emptyQuery),
  useCompanyNotesQuery: vi.fn(() => emptyQuery),
  useCompanyQuotesQuery: vi.fn((_id: string, enabled: boolean) => ({
    ...emptyQuery,
    data: enabled
      ? { items: [
          {
            id: 'quote-internal-id',
            quote_number: 'QUO-2026-000010',
            total_amount: 10000,
            currency: 'INR',
            status: 'Accepted',
            created_at: '2026-09-06T10:00:00Z',
          },
        ], total: 1 }
      : undefined,
  })),
  useCompanyInvoicesQuery: vi.fn(() => emptyQuery),
  useCompanyDocumentsQuery: (...args: unknown[]) => documentsQueryMock(...args),
  useCompanyHierarchyQuery: vi.fn(() => ({ ...emptyQuery, data: undefined })),
  useUpdateCompanyMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteCompanyMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAddCompanyNoteMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('@/lib/api/custom-fields', () => ({
  useEntityCustomFieldsQuery: () => ({
    data: [],
    isLoading: false,
    isError: false,
  }),
}));

import CompanyDetailsPage from './page';

describe('CompanyDetailsPage relationship tabs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    documentsQueryMock.mockImplementation((_id: string, enabled: boolean) => ({
      ...emptyQuery,
      data: enabled ? [] : undefined,
      isError: enabled,
      error: enabled
        ? new ApiError(
            'Company documents are not linked to a CRM entity yet',
            'http',
            501,
            'COMPANY_DOCUMENT_RELATION_UNAVAILABLE',
          )
        : null,
    }));
  });

  it('shows the contacts DataTable without surfacing an inactive Documents failure', () => {
    render(<CompanyDetailsPage />);

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Jane Buyer')).toBeInTheDocument();
    expect(screen.queryByText(/Some related company records/)).not.toBeInTheDocument();
    expect(documentsQueryMock).toHaveBeenCalledWith('company-1', false);
  });

  it('loads the selected tab and renders canonical quote fields', async () => {
    render(<CompanyDetailsPage />);

    await userEvent.click(screen.getByRole('tab', { name: 'Quotes' }));

    expect(screen.getByText('QUO-2026-000010')).toBeInTheDocument();
    expect(screen.queryByText('quote-internal-id')).not.toBeInTheDocument();
  });

  it('isolates the known Documents limitation to the Documents tab', async () => {
    render(<CompanyDetailsPage />);

    await userEvent.click(screen.getByRole('tab', { name: 'Documents' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Documents are not linked to companies yet.',
    );
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });
});
