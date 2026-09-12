import { render, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
const getWithMetadataMock = vi.fn();
const postMock = vi.fn();

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
    getWithMetadata: (...args: unknown[]) => getWithMetadataMock(...args),
    post: (...args: unknown[]) => postMock(...args),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import {
  companyKeys,
  useAddCompanyNoteMutation,
  useCompanyContactsQuery,
  useCompanyDealsQuery,
  useCompanyDocumentsQuery,
  useCompanyHierarchyQuery,
  useCompanyInvoicesQuery,
  useCompanyNotesQuery,
  useCompanyQuotesQuery,
} from './companies';

type RelationshipTab =
  | 'contacts'
  | 'deals'
  | 'notes'
  | 'quotes'
  | 'invoices'
  | 'documents'
  | 'hierarchy';

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
}

function RelationshipQueries({ activeTab }: { activeTab: RelationshipTab }) {
  useCompanyContactsQuery('company-1', activeTab === 'contacts');
  useCompanyDealsQuery('company-1', activeTab === 'deals');
  useCompanyNotesQuery('company-1', activeTab === 'notes');
  useCompanyQuotesQuery('company-1', activeTab === 'quotes');
  useCompanyInvoicesQuery('company-1', activeTab === 'invoices');
  useCompanyDocumentsQuery('company-1', activeTab === 'documents');
  useCompanyHierarchyQuery('company-1', activeTab === 'hierarchy');
  return null;
}

describe('company relationship query hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getWithMetadataMock.mockResolvedValue({
      data: [],
      headers: new Headers({ 'X-Total-Count': '0' }),
      status: 200,
    });
    getMock.mockImplementation(async (endpoint: string) =>
      endpoint.endsWith('/hierarchy') ? { parent_company: null, subsidiaries: [] } : [],
    );
  });

  it('requests only the active relationship tab', async () => {
    const { wrapper } = createWrapper();
    const { rerender } = render(
      <RelationshipQueries activeTab="contacts" />,
      { wrapper },
    );

    await waitFor(() => {
      expect(getWithMetadataMock).toHaveBeenCalledWith(
        '/companies/company-1/contacts?page=1&limit=15',
      );
    });
    expect(getWithMetadataMock).toHaveBeenCalledTimes(1);

    rerender(<RelationshipQueries activeTab="deals" />);

    await waitFor(() => {
      expect(getWithMetadataMock).toHaveBeenCalledWith(
        '/companies/company-1/deals?page=1&limit=15',
      );
    });
    expect(getWithMetadataMock).toHaveBeenCalledTimes(2);
    expect(getMock).not.toHaveBeenCalledWith('/companies/company-1/documents');
  });

  it('invalidates the paginated company-note cache after creating a note', async () => {
    const note = {
      id: 'note-1',
      entity_type: 'company',
      entity_id: 'company-1',
      content: 'Discuss renewal',
      created_by: 'user-1',
      created_at: '2026-09-06T10:00:00Z',
    };
    postMock.mockResolvedValue(note);
    const { client, wrapper } = createWrapper();
    client.setQueryData(companyKeys.notes('company-1', 1, 15), {
      items: [],
      total: 0,
    });
    const { result } = renderHook(() => useAddCompanyNoteMutation('company-1'), {
      wrapper,
    });

    await result.current.mutateAsync('Discuss renewal');

    expect(postMock).toHaveBeenCalledWith(
      '/companies/company-1/notes?content=Discuss%20renewal',
      { content: 'Discuss renewal' },
    );
    expect(client.getQueryState(companyKeys.notes('company-1', 1, 15))?.isInvalidated).toBe(true);
  });
});
