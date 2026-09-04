import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const useLeadsQueryMock = vi.fn();
const bulkDeleteMutateAsync = vi.fn();

const idleMutation = () => ({ mutateAsync: vi.fn(), isPending: false });

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/components/common/permission-gate', () => ({
  PermissionGate: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/api/leads', () => ({
  useLeadsQuery: (...args: unknown[]) => useLeadsQueryMock(...args),
  useCreateLeadMutation: () => idleMutation(),
  useUpdateLeadMutation: () => idleMutation(),
  useDeleteLeadMutation: () => idleMutation(),
  useBulkDeleteLeadsMutation: () => ({ mutateAsync: bulkDeleteMutateAsync, isPending: false }),
  useBulkArchiveLeadsMutation: () => idleMutation(),
  useArchiveLeadMutation: () => idleMutation(),
  useUnarchiveLeadMutation: () => idleMutation(),
  useAssignLeadMutation: () => idleMutation(),
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({ data: undefined, isLoading: false }),
}));

vi.mock('@/lib/api/companies', () => ({
  useCompaniesQuery: () => ({ data: [], isLoading: false }),
}));

vi.mock('@/lib/api/users', () => ({
  useUsersQuery: () => ({ data: [], isLoading: false }),
}));

vi.mock('@/lib/api/custom-fields', () => ({
  useEntityCustomFieldsQuery: () => ({ data: [], isLoading: false, isError: false }),
}));

import LeadsPage from './page';

const lead = {
  id: 'lead-1',
  title: 'Enterprise renewal',
  company: 'Acme',
  contact_name: 'Jane Doe',
  email: 'jane@acme.test',
  status: 'new',
  source: 'https://acme.test',
  score: 75,
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.setItem('user', JSON.stringify({ permissions: ['all'] }));
  useLeadsQueryMock.mockReturnValue({
    data: { items: [lead], total: 1 },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });
  bulkDeleteMutateAsync.mockResolvedValue({ affected_count: 1, message: 'Deleted' });
});

describe('LeadsPage list UX', () => {
  it('normalizes display values and renders a single-plus create action', () => {
    render(<LeadsPage />);

    expect(screen.getByRole('button', { name: 'Add New Lead' })).toHaveTextContent(/^Add New Lead$/);
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('Website')).toHaveAttribute('title', 'https://acme.test');
    expect(screen.getByRole('button', { name: 'Status' })).toBeInTheDocument();
  });

  it('requires confirmation before executing bulk delete', async () => {
    const user = userEvent.setup();
    render(<LeadsPage />);

    await user.click(screen.getByRole('checkbox', { name: 'Select Jane Doe' }));
    await user.click(screen.getByRole('button', { name: /Bulk Actions/ }));
    await user.click(await screen.findByRole('menuitem', { name: 'Bulk Delete (1)' }));

    expect(bulkDeleteMutateAsync).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toHaveTextContent('This bulk action cannot be undone.');

    await user.click(screen.getByRole('button', { name: 'Delete 1 Leads' }));

    await waitFor(() => expect(bulkDeleteMutateAsync).toHaveBeenCalledWith(['lead-1']));
  });

  it('keeps a failed bulk-delete error visible in the confirmation dialog', async () => {
    const user = userEvent.setup();
    bulkDeleteMutateAsync.mockRejectedValueOnce(new Error('Deletion service unavailable'));
    render(<LeadsPage />);

    await user.click(screen.getByRole('checkbox', { name: 'Select Jane Doe' }));
    await user.click(screen.getByRole('button', { name: /Bulk Actions/ }));
    await user.click(await screen.findByRole('menuitem', { name: 'Bulk Delete (1)' }));
    await user.click(screen.getByRole('button', { name: 'Delete 1 Leads' }));

    const dialog = screen.getByRole('dialog');
    expect(await within(dialog).findByText('Deletion service unavailable')).toBeVisible();
  });
});
