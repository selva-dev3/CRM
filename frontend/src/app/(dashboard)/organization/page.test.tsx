import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import OrganizationPage from './page';

const { apiClientMock } = vi.hoisted(() => ({
  apiClientMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock('@/lib/api/client', () => ({
  apiClient: apiClientMock,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({}),
  usePathname: () => '/organization',
}));

const orgs = [
  { id: 'org-1', name: 'Acme Inc', slug: 'acme', status: 'active', plan: 'Enterprise', max_users: 100 },
  { id: 'org-2', name: 'Globex', slug: 'globex', status: 'active', plan: 'Business', max_users: 50 },
];

const roles = [
  { id: 'role-1', name: 'Sales Manager' },
  { id: 'role-2', name: 'Sales Executive' },
];

function mockSuperadminUser() {
  localStorage.setItem('user', JSON.stringify({ role: 'superadmin', email: 'superadmin@gmail.com', permissions: ['invitations:create'] }));
}

function mockApiGet() {
  apiClientMock.get.mockImplementation((url: string) => {
    if (url.startsWith('/organizations/all')) return Promise.resolve(orgs);
    if (url.startsWith('/roles')) return Promise.resolve(roles);
    if (url.startsWith('/organizations/members')) return Promise.resolve([]);
    if (url === '/organizations') return Promise.resolve(orgs[0]);
    return Promise.resolve({});
  });
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <OrganizationPage />
    </QueryClientProvider>
  );
}

async function openInviteModal(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText('Acme Inc');
  await user.click(screen.getAllByRole('button', { name: /Open menu/ })[0]);
  await user.click(await screen.findByRole('button', { name: /Invite Member/ }));
  await screen.findByText('Invite Organization Member');
}

describe('OrganizationPage invite member flow', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    mockSuperadminUser();
    mockApiGet();
    apiClientMock.post.mockResolvedValue({ token: 'inv_abc', invite_url: 'https://app.crm.com/accept-invite/organization/inv_abc', message: 'Invitation sent successfully' });
  });

  it('shows Invite Member action and opens the modal with read-only organization context', async () => {
    const user = userEvent.setup();
    renderPage();

    await openInviteModal(user);

    const dialog = screen.getByText('Invite Organization Member').closest('div.fixed') as HTMLElement;
    expect(within(dialog).getByText('Organization')).toBeInTheDocument();
    expect(within(dialog).getByText('Acme Inc')).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Email Address/)).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: /User Role/ })).toBeInTheDocument();
  });

  it('hides the Invite Member action when the user lacks invitations:create', async () => {
    localStorage.setItem('user', JSON.stringify({ role: 'superadmin', email: 'superadmin@gmail.com', permissions: [] }));
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('Acme Inc');
    await user.click(screen.getAllByRole('button', { name: /Open menu/ })[0]);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Invite Member/ })).not.toBeInTheDocument();
    });
  });

  it('requires a role before sending the invitation', async () => {
    const user = userEvent.setup();
    renderPage();

    await openInviteModal(user);

    const dialog = screen.getByText('Invite Organization Member').closest('div.fixed') as HTMLElement;
    fireEvent.change(within(dialog).getByLabelText(/Email Address/), { target: { value: 'jane@acme.com' } });
    await user.click(within(dialog).getByRole('button', { name: /Send Invitation/ }));

    expect(await screen.findByText('Please select a role.')).toBeInTheDocument();
    expect(apiClientMock.post).not.toHaveBeenCalled();
  });

  it('sends the invitation with the row organization id and shows a success message', async () => {
    const user = userEvent.setup();
    renderPage();

    await openInviteModal(user);

    const dialog = screen.getByText('Invite Organization Member').closest('div.fixed') as HTMLElement;
    fireEvent.change(within(dialog).getByLabelText(/Email Address/), { target: { value: 'jane@acme.com' } });

    await user.click(within(dialog).getByRole('button', { name: /User Role/ }));
    await user.click(await screen.findByRole('option', { name: 'Sales Manager' }));

    await user.click(within(dialog).getByRole('button', { name: /Send Invitation/ }));

    await waitFor(() => {
      expect(apiClientMock.post).toHaveBeenCalledWith(
        '/organizations/invitations',
        expect.objectContaining({ organization_id: 'org-1', email: 'jane@acme.com', role: 'role-1' })
      );
    });
    expect(await screen.findByText(/Invitation sent successfully to jane@acme.com/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('Invite Organization Member')).not.toBeInTheDocument();
    });
  });

  it('keeps the modal open and shows the error message when the invite fails', async () => {
    apiClientMock.post.mockRejectedValue(new Error('User with email already active.'));
    const user = userEvent.setup();
    renderPage();

    await openInviteModal(user);

    const dialog = screen.getByText('Invite Organization Member').closest('div.fixed') as HTMLElement;
    fireEvent.change(within(dialog).getByLabelText(/Email Address/), { target: { value: 'jane@acme.com' } });

    await user.click(within(dialog).getByRole('button', { name: /User Role/ }));
    await user.click(await screen.findByRole('option', { name: 'Sales Manager' }));

    await user.click(within(dialog).getByRole('button', { name: /Send Invitation/ }));

    expect(await screen.findByText('User with email already active.')).toBeInTheDocument();
    expect(screen.getByText('Invite Organization Member')).toBeInTheDocument();
  });
});
