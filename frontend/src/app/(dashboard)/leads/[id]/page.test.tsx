import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const useLeadQueryMock = vi.fn();
const useUsersQueryMock = vi.fn();
const updateLeadMutateAsync = vi.fn();
const assignLeadApiMock = vi.fn();
const refetchLeadMock = vi.fn();
const refetchUsersMock = vi.fn();

const emptyQuery = {
  data: [],
  isLoading: false,
  refetch: vi.fn(),
};

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'lead-1' }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock('@/components/ui/select', () => ({
  Select: ({
    value,
    onValueChange,
    disabled,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    disabled?: boolean;
    children: ReactNode;
  }) => (
    <select
      aria-label="Select sales representative"
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
      disabled={disabled}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}));

vi.mock('@/lib/api/client', () => ({ BASE_URL: 'http://localhost:3000/api/v1' }));

vi.mock('@/lib/api/leads', () => ({
  useLeadQuery: (...args: unknown[]) => useLeadQueryMock(...args),
  useCreateLeadMutation: () => ({ mutateAsync: vi.fn() }),
  useUpdateLeadMutation: () => ({ mutateAsync: updateLeadMutateAsync }),
  useDeleteLeadMutation: () => ({ mutateAsync: vi.fn() }),
  useLeadNotesQuery: () => emptyQuery,
  useLeadTasksQuery: () => emptyQuery,
  useLeadEmailsQuery: () => emptyQuery,
  useLeadCallsQuery: () => emptyQuery,
  useLeadDocumentsQuery: () => emptyQuery,
  addLeadNoteApi: vi.fn(),
  createLeadTaskApi: vi.fn(),
  sendLeadEmailApi: vi.fn(),
  logLeadCallApi: vi.fn(),
  uploadLeadDocumentApi: vi.fn(),
  recalculateLeadScoreApi: vi.fn(),
  convertLeadApi: vi.fn(),
  assignLeadApi: (...args: unknown[]) => assignLeadApiMock(...args),
  archiveLeadApi: vi.fn(),
  unarchiveLeadApi: vi.fn(),
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({
    data: [{ id: 'org-1', name: 'Acme Organization', timezone: 'Asia/Kolkata' }],
    isLoading: false,
  }),
}));

vi.mock('@/lib/api/companies', () => ({
  useCompaniesQuery: () => ({ data: [], isLoading: false }),
}));

vi.mock('@/lib/api/users', () => ({
  useUsersQuery: (...args: unknown[]) => useUsersQueryMock(...args),
}));

import LeadDetailPage from './page';

const lead = {
  id: 'lead-1',
  title: 'Enterprise renewal',
  company: 'Acme',
  contact_name: 'Jane Doe',
  email: 'jane@acme.test',
  phone: '555-0100',
  status: 'New',
  source: 'Website',
  score: 75,
  organization_id: 'org-1',
  assigned_to: 'user-1',
  is_archived: false,
  created_at: '2026-08-31T20:00:00Z',
};

const users = [
  { id: 'user-1', name: 'Alex Agent', email: 'alex@example.test', role: 'sales_rep' },
  { id: 'user-2', name: 'Sam Seller', email: 'sam@example.test', role: 'sales_rep' },
];

async function openActionsTab() {
  await userEvent.click(screen.getByRole('button', { name: /Actions & Convert/ }));
}

beforeEach(() => {
  vi.clearAllMocks();
  refetchLeadMock.mockResolvedValue({ data: lead });
  refetchUsersMock.mockResolvedValue({ data: users });
  updateLeadMutateAsync.mockResolvedValue({ ...lead, assigned_to: null });
  assignLeadApiMock.mockResolvedValue({ message: 'Assigned', status: 'success' });
  useLeadQueryMock.mockReturnValue({
    data: lead,
    isLoading: false,
    isError: false,
    error: null,
    refetch: refetchLeadMock,
  });
  useUsersQueryMock.mockReturnValue({
    data: users,
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: refetchUsersMock,
  });
});

describe('LeadDetailPage assignment UX', () => {
  it('shows the current assignee and disables an unchanged assignment', async () => {
    render(<LeadDetailPage />);
    await openActionsTab();

    expect(screen.getByRole('combobox', { name: 'Select sales representative' })).toHaveValue('user-1');
    expect(screen.getByRole('button', { name: 'Assign Lead' })).toBeDisabled();
  });

  it('unassigns the lead through the existing update API', async () => {
    const user = userEvent.setup();
    render(<LeadDetailPage />);
    await openActionsTab();

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Select sales representative' }),
      '__unassigned__',
    );
    await user.click(screen.getByRole('button', { name: 'Unassign Lead' }));

    await waitFor(() => {
      expect(updateLeadMutateAsync).toHaveBeenCalledWith({
        id: 'lead-1',
        payload: { assigned_to: null },
      });
    });
    expect(assignLeadApiMock).not.toHaveBeenCalled();
  });

  it('assigns an unassigned lead through the assignment API', async () => {
    const user = userEvent.setup();
    useLeadQueryMock.mockReturnValue({
      data: { ...lead, assigned_to: null },
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchLeadMock,
    });
    render(<LeadDetailPage />);
    await openActionsTab();

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Select sales representative' }),
      'user-2',
    );
    await user.click(screen.getByRole('button', { name: 'Assign Lead' }));

    await waitFor(() => expect(assignLeadApiMock).toHaveBeenCalledWith('lead-1', 'user-2'));
    expect(updateLeadMutateAsync).not.toHaveBeenCalled();
  });

  it('surfaces a users-query error and provides a retry action', async () => {
    const user = userEvent.setup();
    useLeadQueryMock.mockReturnValue({
      data: { ...lead, assigned_to: null },
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchLeadMock,
    });
    useUsersQueryMock.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      isError: true,
      refetch: refetchUsersMock,
    });
    render(<LeadDetailPage />);
    await openActionsTab();

    expect(screen.getByRole('alert')).toHaveTextContent('Sales representatives could not be loaded.');
    expect(screen.getByRole('combobox', { name: 'Select sales representative' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refetchUsersMock).toHaveBeenCalledOnce();
  });

  it('distinguishes loading and empty user states', async () => {
    useLeadQueryMock.mockReturnValue({
      data: { ...lead, assigned_to: null },
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchLeadMock,
    });
    useUsersQueryMock.mockReturnValue({
      data: [],
      isLoading: true,
      isFetching: true,
      isError: false,
      refetch: refetchUsersMock,
    });
    const { rerender } = render(<LeadDetailPage />);
    await openActionsTab();

    expect(screen.getByRole('status')).toHaveTextContent('Loading sales representatives...');
    expect(screen.getByRole('combobox', { name: 'Select sales representative' })).toBeDisabled();

    useUsersQueryMock.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      isError: false,
      refetch: refetchUsersMock,
    });
    rerender(<LeadDetailPage />);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByText('No sales representatives are available for assignment.')).toBeVisible();
  });
});
