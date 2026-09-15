import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { replaceMock, refetchMock, searchParamsMock, useContactsPageQueryMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  refetchMock: vi.fn(),
  searchParamsMock: { current: '' },
  useContactsPageQueryMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/contacts',
  useRouter: () => ({ push: vi.fn(), replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(searchParamsMock.current),
}));

vi.mock('@/components/common/permission-gate', () => ({
  PermissionGate: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/api/contacts', () => ({
  useContactsPageQuery: (...args: unknown[]) => useContactsPageQueryMock(...args),
  useCreateContactMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateContactMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteContactMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useStarContactMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUnstarContactMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useMergeContactsMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useBulkDeleteContactsMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useImportContactsCsvMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  exportContactsCsvApi: vi.fn(),
}));

vi.mock('@/lib/api/companies', () => ({
  useCompaniesQuery: () => ({ data: [{ id: 'company-1', name: 'Acme' }] }),
}));

vi.mock('@/lib/api/users', () => ({
  useUsersQuery: () => ({ data: [{ id: 'owner-1', name: 'Alex Owner' }] }),
}));

vi.mock('@/lib/api/custom-fields', () => ({
  useEntityCustomFieldsQuery: () => ({ data: [], isLoading: false, isError: false }),
}));

import { updateContactDirectoryParams } from '@/components/features/contacts/contact-directory-params';
import ContactsPage from './page';

const contact = {
  id: 'contact-1',
  name: 'Jane Doe',
  email: 'jane@example.com',
  phone: '+1 555 0100',
  position: 'Design Manager',
  company_id: 'company-outside-filter-page',
  company_name: 'Dribbble',
  owner_id: 'owner-outside-filter-page',
  owner_name: 'Morgan Lee',
  is_starred: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  searchParamsMock.current = '';
  useContactsPageQueryMock.mockReturnValue({
    data: { items: [contact], total: 1 },
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: refetchMock,
  });
});

describe('ContactsPage directory UX', () => {
  it('renders API-resolved company and owner labels in the compact directory table', () => {
    render(<ContactsPage />);

    expect(screen.getByRole('heading', { name: 'Contacts' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create Contact' })).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('Dribbble')).toBeInTheDocument();
    expect(screen.getByText('Morgan Lee')).toBeInTheDocument();
    expect(screen.queryByText('company-outside-filter-page')).not.toBeInTheDocument();
  });

  it('renders a local loading state without removing directory controls', () => {
    useContactsPageQueryMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: true,
      isError: false,
      refetch: refetchMock,
    });

    render(<ContactsPage />);

    expect(screen.getByText('Loading contacts')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create Contact' })).toBeInTheDocument();
  });

  it('shows an actionable API error and retries only the contacts query', async () => {
    const user = userEvent.setup();
    useContactsPageQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
      refetch: refetchMock,
    });

    render(<ContactsPage />);
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(refetchMock).toHaveBeenCalledTimes(1);
  });

  it('stores the starred view in the URL', async () => {
    const user = userEvent.setup();
    render(<ContactsPage />);

    await user.click(screen.getByRole('tab', { name: 'Starred' }));

    expect(replaceMock).toHaveBeenCalledWith('/contacts?view=starred', { scroll: false });
  });

  it('recovers an out-of-range deep link to the final available page', async () => {
    searchParamsMock.current = 'page=99';
    useContactsPageQueryMock.mockReturnValue({
      data: { items: [], total: 20 },
      isLoading: false,
      isFetching: false,
      isError: false,
      refetch: refetchMock,
    });

    render(<ContactsPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/contacts?page=2', { scroll: false });
    });
  });

  it('preserves rapid filter updates before navigation commits', () => {
    let pendingParams = '';
    pendingParams = updateContactDirectoryParams(pendingParams, { company: 'company-1' });
    pendingParams = updateContactDirectoryParams(pendingParams, { owner: 'owner-1' });

    expect(pendingParams).toBe('company=company-1&owner=owner-1');
  });
});
