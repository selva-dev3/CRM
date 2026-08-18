import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

const useUsersQueryMock = vi.fn();
const useUserInvitationsQueryMock = vi.fn();
const useCreateUserMutationMock = vi.fn();
const useInviteUsersMutationMock = vi.fn();
const useActivateUserMutationMock = vi.fn();
const useDeactivateUserMutationMock = vi.fn();
const useDeleteUserMutationMock = vi.fn();
const deactivateUserApiMock = vi.fn();
const deleteUserApiMock = vi.fn();
const useOrganizationsQueryMock = vi.fn();
const createMutateAsyncMock = vi.fn();
const inviteMutateAsyncMock = vi.fn();
const queryClientMock = { invalidateQueries: vi.fn() };

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => queryClientMock,
}));

vi.mock('@/lib/api/users', () => ({
  useUsersQuery: (...args: unknown[]) => useUsersQueryMock(...args),
  useUserInvitationsQuery: (...args: unknown[]) => useUserInvitationsQueryMock(...args),
  useCreateUserMutation: (...args: unknown[]) => useCreateUserMutationMock(...args),
  useInviteUsersMutation: (...args: unknown[]) => useInviteUsersMutationMock(...args),
  useActivateUserMutation: (...args: unknown[]) => useActivateUserMutationMock(...args),
  useDeactivateUserMutation: (...args: unknown[]) => useDeactivateUserMutationMock(...args),
  useDeleteUserMutation: (...args: unknown[]) => useDeleteUserMutationMock(...args),
  deactivateUserApi: (...args: unknown[]) => deactivateUserApiMock(...args),
  deleteUserApi: (...args: unknown[]) => deleteUserApiMock(...args),
}));

vi.mock('@/lib/api/organizations', () => ({
  useOrganizationsQuery: (...args: unknown[]) => useOrganizationsQueryMock(...args),
}));

vi.mock('@/components/common/permission-gate', () => ({
  PermissionGate: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/common/data-table', () => ({
  DataTable: () => <div data-testid="data-table" />,
}));

vi.mock('@/components/common/confirm-modal', () => ({
  ConfirmModal: () => null,
}));

vi.mock('@/components/features/users/role-search-combobox', () => ({
  RoleSearchCombobox: ({ id, value, onChange }: { id?: string; value?: string; onChange?: (value: string) => void }) => (
    <select id={id} value={value ?? ''} onChange={(e) => onChange?.(e.target.value)}>
      <option value="">Select a role</option>
      <option value="role-1">Sales Manager</option>
      <option value="role-2">Sales Executive</option>
    </select>
  ),
}));

import UsersPage from './page';

beforeEach(() => {
  vi.clearAllMocks();
  useUsersQueryMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
  useUserInvitationsQueryMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
  useOrganizationsQueryMock.mockReturnValue({ data: [], isLoading: false, isError: false });
  useCreateUserMutationMock.mockReturnValue({ mutateAsync: createMutateAsyncMock });
  useInviteUsersMutationMock.mockReturnValue({ mutateAsync: inviteMutateAsyncMock });
  useActivateUserMutationMock.mockReturnValue({ mutateAsync: vi.fn() });
  useDeactivateUserMutationMock.mockReturnValue({ mutateAsync: vi.fn() });
  useDeleteUserMutationMock.mockReturnValue({ mutateAsync: vi.fn() });
  createMutateAsyncMock.mockReset().mockResolvedValue({
    id: 'u1',
    name: 'Jordan Lee',
    email: 'jordan@crm.com',
    role: 'role-2',
    organization_id: 'org-1',
    is_active: true,
    created_at: '2026-08-01T00:00:00Z',
  });
  inviteMutateAsyncMock.mockReset().mockResolvedValue({
    message: 'Invitation sent',
    invitations: [],
    status: 'success',
  });
});

async function openInviteModal(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /Invite User/ }));
}

describe('UsersPage invite modal', () => {
  it('shows no Organization field and submits the selected role id', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    await openInviteModal(user);

    expect(screen.getByText('Invite Team Member')).toBeInTheDocument();
    expect(screen.queryByText('Organization')).not.toBeInTheDocument();

    await user.type(screen.getByLabelText(/Full Name/), 'Alex Rivera');
    await user.type(screen.getByLabelText(/Email Address/), 'alex@crm.com');
    await user.selectOptions(screen.getByLabelText(/User Role/), 'role-1');

    await user.click(screen.getByRole('button', { name: /Send Invitation/ }));

    await waitFor(() => {
      expect(inviteMutateAsyncMock).toHaveBeenCalledTimes(1);
    });
    expect(inviteMutateAsyncMock).toHaveBeenCalledWith({
      users: [{ name: 'Alex Rivera', email: 'alex@crm.com' }],
      role: 'role-1',
    });
    expect(inviteMutateAsyncMock.mock.calls[0][0]).not.toHaveProperty('organization_id');

    expect(await screen.findByText(/Invitation sent successfully to alex@crm.com/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('Invite Team Member')).not.toBeInTheDocument();
    });
  });

  it('shows a validation error and does not call the API when no role is selected', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    await openInviteModal(user);

    await user.type(screen.getByLabelText(/Full Name/), 'Alex Rivera');
    await user.type(screen.getByLabelText(/Email Address/), 'alex@crm.com');

    await user.click(screen.getByRole('button', { name: /Send Invitation/ }));

    expect(await screen.findByText('Please select a role.')).toBeInTheDocument();
    expect(inviteMutateAsyncMock).not.toHaveBeenCalled();
    expect(screen.getByText('Invite Team Member')).toBeInTheDocument();
  });

  it('keeps the modal open and shows the error when the invite request fails', async () => {
    const user = userEvent.setup();
    inviteMutateAsyncMock.mockRejectedValueOnce(new Error('Server error'));
    render(<UsersPage />);
    await openInviteModal(user);

    await user.type(screen.getByLabelText(/Email Address/), 'alex@crm.com');
    await user.selectOptions(screen.getByLabelText(/User Role/), 'role-1');

    await user.click(screen.getByRole('button', { name: /Send Invitation/ }));

    expect(await screen.findByText('Server error')).toBeInTheDocument();
    expect(screen.getByText('Invite Team Member')).toBeInTheDocument();
    expect(screen.getByLabelText(/Email Address/)).toHaveValue('alex@crm.com');
  });
});

describe('UsersPage create user form', () => {
  it('submits name, email, default password and the selected role id', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await user.click(screen.getByRole('button', { name: /Create User/ }));
    expect(screen.getByText('Create New User Account')).toBeInTheDocument();
    expect(screen.queryByText('Organization')).not.toBeInTheDocument();

    await user.type(screen.getByLabelText(/Full Name/), 'Jordan Lee');
    await user.type(screen.getByLabelText(/Email Address/), 'jordan@crm.com');
    await user.selectOptions(screen.getByLabelText(/User Role/), 'role-2');

    await user.click(screen.getByRole('button', { name: /Create User Account/ }));

    await waitFor(() => {
      expect(createMutateAsyncMock).toHaveBeenCalledTimes(1);
    });
    expect(createMutateAsyncMock).toHaveBeenCalledWith({
      name: 'Jordan Lee',
      email: 'jordan@crm.com',
      password: 'Password123!',
      role: 'role-2',
    });
    expect(createMutateAsyncMock.mock.calls[0][0]).not.toHaveProperty('organization_id');

    expect(await screen.findByText(/User account "Jordan Lee" created successfully/)).toBeInTheDocument();
  });

  it('requires a role before submitting', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await user.click(screen.getByRole('button', { name: /Create User/ }));
    await user.type(screen.getByLabelText(/Full Name/), 'Jordan Lee');
    await user.type(screen.getByLabelText(/Email Address/), 'jordan@crm.com');

    await user.click(screen.getByRole('button', { name: /Create User Account/ }));

    expect(await screen.findByText('Please select a role.')).toBeInTheDocument();
    expect(createMutateAsyncMock).not.toHaveBeenCalled();
  });
});