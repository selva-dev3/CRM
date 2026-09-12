import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS } from '@/lib/permissions';

const useLeadQueryMock = vi.fn();
const useUsersQueryMock = vi.fn();
const updateLeadMutateAsync = vi.fn();
const assignLeadApiMock = vi.fn();
const qualifyLeadApiMock = vi.fn();
const sendLeadEmailApiMock = vi.fn();
const createLeadTaskApiMock = vi.fn();
const useLeadTimelineQueryMock = vi.fn();
const useLeadEmailsQueryMock = vi.fn();
const useLeadCallsQueryMock = vi.fn();
const refetchLeadMock = vi.fn();
const refetchUsersMock = vi.fn();
const customFieldsQueryMock = vi.fn();

const emptyQuery = {
  data: { items: [], total: 0 },
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
  useLeadTimelineQuery: (...args: unknown[]) => useLeadTimelineQueryMock(...args),
  useCreateLeadMutation: () => ({ mutateAsync: vi.fn() }),
  useUpdateLeadMutation: () => ({ mutateAsync: updateLeadMutateAsync }),
  useDeleteLeadMutation: () => ({ mutateAsync: vi.fn() }),
  useLeadNotesQuery: () => emptyQuery,
  useLeadTasksQuery: () => emptyQuery,
  useLeadEmailsQuery: (...args: unknown[]) => useLeadEmailsQueryMock(...args),
  useLeadCallsQuery: (...args: unknown[]) => useLeadCallsQueryMock(...args),
  useLeadDocumentsQuery: () => emptyQuery,
  addLeadNoteApi: vi.fn(),
  createLeadTaskApi: (...args: unknown[]) => createLeadTaskApiMock(...args),
  sendLeadEmailApi: (...args: unknown[]) => sendLeadEmailApiMock(...args),
  logLeadCallApi: vi.fn(),
  uploadLeadDocumentApi: vi.fn(),
  recalculateLeadScoreApi: vi.fn(),
  convertLeadApi: vi.fn(),
  qualifyLeadApi: (...args: unknown[]) => qualifyLeadApiMock(...args),
  disqualifyLeadApi: vi.fn(),
  reopenLeadApi: vi.fn(),
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

vi.mock('@/lib/api/custom-fields', () => ({
  useEntityCustomFieldsQuery: () => customFieldsQueryMock(),
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
  custom_fields: { territory: 'North' },
};

const users = [
  { id: 'user-1', name: 'Alex Agent', email: 'alex@example.test', role: 'sales_rep' },
  { id: 'user-2', name: 'Sam Seller', email: 'sam@example.test', role: 'sales_rep' },
];

async function openActionsTab() {
  await userEvent.click(screen.getByRole('tab', { name: /Actions & Convert/ }));
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.setItem('user', JSON.stringify({
    permissions: Object.values(PERMISSIONS).flatMap((group) => Object.values(group)),
  }));
  refetchLeadMock.mockResolvedValue({ data: lead });
  refetchUsersMock.mockResolvedValue({ data: users });
  updateLeadMutateAsync.mockResolvedValue({ ...lead, assigned_to: null });
  assignLeadApiMock.mockResolvedValue({ message: 'Assigned', status: 'success' });
  qualifyLeadApiMock.mockResolvedValue({ ...lead, status: 'Qualified' });
  sendLeadEmailApiMock.mockResolvedValue({
    id: 'email-1',
    from_email: 'rep@crm.test',
    to: [lead.email],
    subject: 'Hello',
    status: 'Pending',
    sent_at: null,
  });
  createLeadTaskApiMock.mockResolvedValue({ id: 'task-1' });
  useLeadTimelineQueryMock.mockReturnValue(emptyQuery);
  useLeadEmailsQueryMock.mockReturnValue(emptyQuery);
  useLeadCallsQueryMock.mockReturnValue(emptyQuery);
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
  customFieldsQueryMock.mockReturnValue({
    data: [
      { field_name: 'territory', field_type: 'text', label: 'Territory', options: [] },
    ],
    isLoading: false,
    isError: false,
  });
});

describe('LeadDetailPage call permissions', () => {
  it('hides the Calls tab and disables its query without calls:read', () => {
    window.localStorage.setItem(
      'user',
      JSON.stringify({ permissions: ['leads:read'] }),
    );

    render(<LeadDetailPage />);

    expect(screen.queryByRole('tab', { name: /Calls/ })).not.toBeInTheDocument();
    expect(useLeadCallsQueryMock).toHaveBeenCalledWith('lead-1', false, 1, 15);
  });
});

describe('LeadDetailPage custom fields', () => {
  it('loads and submits custom fields from the edit modal', async () => {
    const user = userEvent.setup();
    render(<LeadDetailPage />);

    await user.click(screen.getByRole('button', { name: 'Edit Lead' }));
    expect(screen.getByLabelText('Territory')).toHaveValue('North');
    await user.clear(screen.getByLabelText('Territory'));
    await user.type(screen.getByLabelText('Territory'), 'South');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(updateLeadMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'lead-1',
          payload: expect.objectContaining({ custom_fields: { territory: 'South' } }),
        }),
      );
    });
  });
});

describe('LeadDetailPage email workflow', () => {
  it('renders expandable email history with the message body', async () => {
    const user = userEvent.setup();
    useLeadEmailsQueryMock.mockReturnValue({
      data: { items: [{
        id: 'email-1',
        from_email: 'rep@crm.test',
        to: [lead.email],
        subject: 'Proposal follow-up',
        body: '<p>Hello Jane,</p><p>Please review the proposal.</p>',
        status: 'Sent',
        sent_at: '2026-09-07T17:00:00Z',
      }], total: 1 },
      isLoading: false,
      refetch: vi.fn(),
    });
    render(<LeadDetailPage />);

    await user.click(screen.getByRole('tab', { name: /Emails/ }));

    expect(screen.getByText('Proposal follow-up')).toBeVisible();
    expect(screen.queryByText(/Please review the proposal/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Expand row' }));

    expect(screen.getByText(/Hello Jane,/)).toBeVisible();
    expect(screen.getByText(/Please review the proposal/)).toBeVisible();
  });

  it('shows the Lead recipient and reports queued delivery', async () => {
    const user = userEvent.setup();
    render(<LeadDetailPage />);

    await user.click(screen.getByRole('tab', { name: /Emails/ }));
    await user.click(screen.getByRole('button', { name: 'Send Email' }));

    expect(screen.getByText('The Lead\'s primary email is used as the recipient.')).toBeVisible();
    expect(screen.getByText('jane@acme.test')).toBeVisible();

    await user.type(screen.getByPlaceholderText('Enterprise CRM Proposal & Next Steps'), 'Hello');
    await user.type(screen.getByPlaceholderText('Hi, following up on our recent demo...'), 'Hi Jane');
    const sendButtons = screen.getAllByRole('button', { name: 'Send Email' });
    await user.click(sendButtons[sendButtons.length - 1]);

    await waitFor(() => {
      expect(sendLeadEmailApiMock).toHaveBeenCalledWith(
        'lead-1',
        { to: ['jane@acme.test'], subject: 'Hello', body: 'Hi Jane' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Email queued for delivery.')).toBeVisible();
  });

  it('blocks sending when the Lead has no valid email', async () => {
    const user = userEvent.setup();
    useLeadQueryMock.mockReturnValue({
      data: { ...lead, email: '' },
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchLeadMock,
    });
    render(<LeadDetailPage />);

    await user.click(screen.getByRole('tab', { name: /Emails/ }));
    await user.click(screen.getByRole('button', { name: 'Send Email' }));

    expect(await screen.findByText('This lead does not have a valid email address.')).toBeVisible();
    expect(sendLeadEmailApiMock).not.toHaveBeenCalled();
  });
});

describe('LeadDetailPage task workflow', () => {
  it('shows an associated error when the shared due-date picker is empty', async () => {
    const user = userEvent.setup();
    render(<LeadDetailPage />);
    await user.click(screen.getByRole('tab', { name: /Tasks/ }));
    await user.click(screen.getByRole('button', { name: 'Create Task' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByPlaceholderText('Schedule follow-up call'), 'Call customer');
    const dueDatePicker = within(dialog).getByLabelText('Follow-up Due Date *');

    await user.click(within(dialog).getByRole('button', { name: 'Create Task' }));

    expect(await within(dialog).findByText('Follow-up due date is required.')).toBeVisible();
    expect(dueDatePicker).toHaveAttribute('aria-invalid', 'true');
    expect(dueDatePicker).toHaveAttribute('aria-describedby', 'lead-task-error');
    expect(createLeadTaskApiMock).not.toHaveBeenCalled();
  });
});

describe('LeadDetailPage assignment UX', () => {
  it('shows the current assignee and disables an unchanged assignment', async () => {
    render(<LeadDetailPage />);
    await openActionsTab();

    expect(screen.getByRole('combobox', { name: 'Select sales representative' })).toHaveValue('user-1');
    expect(screen.getByRole('button', { name: 'Assign Lead' })).toBeDisabled();
  });

  it('unassigns the lead through the permission-protected assignment API', async () => {
    const user = userEvent.setup();
    render(<LeadDetailPage />);
    await openActionsTab();

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Select sales representative' }),
      '__unassigned__',
    );
    await user.click(screen.getByRole('button', { name: 'Unassign Lead' }));

    await waitFor(() => {
      expect(assignLeadApiMock).toHaveBeenCalledWith('lead-1', null);
    });
    expect(updateLeadMutateAsync).not.toHaveBeenCalled();
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

describe('LeadDetailPage lifecycle', () => {
  it('qualifies a lead through the dedicated lifecycle API', async () => {
    const user = userEvent.setup();
    render(<LeadDetailPage />);
    await openActionsTab();

    await user.click(screen.getByRole('button', { name: 'Qualify Lead' }));
    await user.type(screen.getByLabelText(/Reason/), 'Budget and authority confirmed');
    const qualifyButtons = screen.getAllByRole('button', { name: 'Qualify Lead' });
    await user.click(qualifyButtons[qualifyButtons.length - 1]);

    await waitFor(() => {
      expect(qualifyLeadApiMock).toHaveBeenCalledWith(
        'lead-1',
        'Budget and authority confirmed',
      );
    });
  });

  it('renders the unified activity timeline', async () => {
    useLeadTimelineQueryMock.mockReturnValue({
      data: { items: [{
        id: 'activity-1',
        event_type: 'lead_qualified',
        title: 'Lead qualified',
        description: 'Budget confirmed',
        timestamp: '2026-09-06T10:00:00Z',
      }], total: 1 },
      isLoading: false,
      refetch: vi.fn(),
    });
    const user = userEvent.setup();
    render(<LeadDetailPage />);

    await user.click(screen.getByRole('tab', { name: /Timeline/ }));
    expect(screen.getByText('Budget confirmed')).toBeVisible();
  });
});
