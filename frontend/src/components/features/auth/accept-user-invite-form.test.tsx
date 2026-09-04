import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AcceptUserInviteForm } from './accept-user-invite-form';

const mocks = vi.hoisted(() => ({
  acceptMutateAsync: vi.fn(),
  replace: vi.fn(),
  searchToken: 'ABCDEFGHIJKLMN',
  invitationQuery: {
    data: {
      id: 'inv-1',
      email: 'manager@crm.com',
      role: 'Sales Manager',
      status: 'pending',
      organization_id: 'org-1',
      created_at: '2026-09-04T00:00:00Z',
    } as {
      id: string;
      email: string;
      role: string;
      status: string;
      organization_id: string;
      created_at: string;
    } | undefined,
    isLoading: false,
    isError: false,
  },
  useAcceptInviteMutation: vi.fn(),
  useUserInvitationDetailsQuery: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace }),
  useSearchParams: () => ({ get: () => mocks.searchToken }),
}));

vi.mock('@/lib/api', () => ({
  useAcceptInviteMutation: () => mocks.useAcceptInviteMutation(),
  useUserInvitationDetailsQuery: (token: string) =>
    mocks.useUserInvitationDetailsQuery(token),
}));

describe('AcceptUserInviteForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    mocks.searchToken = 'ABCDEFGHIJKLMN';
    mocks.invitationQuery.data = {
      id: 'inv-1',
      email: 'manager@crm.com',
      role: 'Sales Manager',
      status: 'pending',
      organization_id: 'org-1',
      created_at: '2026-09-04T00:00:00Z',
    };
    mocks.invitationQuery.isLoading = false;
    mocks.invitationQuery.isError = false;
    mocks.useUserInvitationDetailsQuery.mockReturnValue(mocks.invitationQuery);
    mocks.useAcceptInviteMutation.mockReturnValue({
      isPending: false,
      mutateAsync: mocks.acceptMutateAsync,
    });
  });

  it('loads the invitation and renders server-controlled email and role', () => {
    render(<AcceptUserInviteForm />);

    expect(mocks.useUserInvitationDetailsQuery).toHaveBeenCalledWith('ABCDEFGHIJKLMN');
    expect(screen.getByText('Sales Manager')).toBeInTheDocument();
    expect(screen.getByText('manager@crm.com')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: /email/i })).not.toBeInTheDocument();
  });

  it('rejects mismatched passwords without calling the API', async () => {
    const user = userEvent.setup();
    render(<AcceptUserInviteForm />);

    await user.type(screen.getByLabelText('Full name'), 'Alex Manager');
    await user.type(screen.getByLabelText('Password'), 'secure-password');
    await user.type(screen.getByLabelText('Confirm password'), 'different-password');
    await user.click(screen.getByRole('button', { name: 'Accept invitation' }));

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
    expect(mocks.acceptMutateAsync).not.toHaveBeenCalled();
  });

  it('accepts the invitation, stores the resolved user, and redirects', async () => {
    const user = userEvent.setup();
    const acceptedUser = {
      id: 'user-1',
      name: 'Alex Manager',
      email: 'manager@crm.com',
      role: 'Sales Manager',
      organization_id: 'org-1',
      permissions: ['dashboard:read'],
    };
    mocks.acceptMutateAsync.mockResolvedValue({
      message: 'accepted',
      access_token: 'cookie-token',
      token_type: 'bearer',
      user_id: acceptedUser.id,
      email: acceptedUser.email,
      name: acceptedUser.name,
      role: acceptedUser.role,
      status: 'success',
      user: acceptedUser,
    });
    render(<AcceptUserInviteForm />);

    await user.type(screen.getByLabelText('Full name'), 'Alex Manager');
    await user.type(screen.getByLabelText('Password'), 'secure-password');
    await user.type(screen.getByLabelText('Confirm password'), 'secure-password');
    await user.click(screen.getByRole('button', { name: 'Accept invitation' }));

    await waitFor(() => {
      expect(mocks.acceptMutateAsync).toHaveBeenCalledWith({
        token: 'ABCDEFGHIJKLMN',
        name: 'Alex Manager',
        password: 'secure-password',
      });
    });
    expect(JSON.parse(sessionStorage.getItem('user') ?? '{}')).toEqual(acceptedUser);
    expect(localStorage.getItem('user')).toBeNull();
    expect(mocks.replace).toHaveBeenCalledWith('/dashboard');
  });

  it('shows an error when the token is missing', () => {
    mocks.searchToken = '';

    render(<AcceptUserInviteForm />);

    expect(screen.getByText('Invalid invitation link')).toBeInTheDocument();
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument();
  });

  it('does not render the form for an accepted invitation', () => {
    if (mocks.invitationQuery.data) {
      mocks.invitationQuery.data.status = 'accepted';
    }

    render(<AcceptUserInviteForm />);

    expect(screen.getByText('Invitation already used')).toBeInTheDocument();
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument();
  });
});
