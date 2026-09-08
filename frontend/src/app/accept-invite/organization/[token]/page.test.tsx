import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ accept: vi.fn(), push: vi.fn() }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push }), useParams: () => ({ token: 'invitation-token' }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock('@/lib/api/organizations', () => ({
  useValidateInvitationQuery: () => ({ data: { is_valid: true, full_name: 'Invited User', email: 'invited@example.com', organization: { name: 'Existing organization' } }, isLoading: false }),
  useAcceptInvitationMutation: () => ({ mutateAsync: mocks.accept, isPending: false }),
}));
import Page from './page';

describe('organization invitation acceptance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('collects only the invited account details without editing the organization', async () => {
    mocks.accept.mockRejectedValue(new Error('Controlled failure'));
    render(<Page />);
    expect(screen.queryByLabelText(/Organization Name/)).not.toBeInTheDocument();
    expect(screen.queryByText('1-Click Demo Fill')).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Set Account Password *'), 'controlled-test-password');
    await userEvent.click(screen.getByRole('button', { name: 'Accept Invitation' }));
    await waitFor(() => expect(mocks.accept).toHaveBeenCalledWith({
      token: 'invitation-token', payload: { password: 'controlled-test-password', full_name: 'Invited User' },
    }));
    expect(await screen.findByText('Controlled failure')).toBeInTheDocument();
    expect(screen.getByLabelText('Set Account Password *')).toHaveValue('controlled-test-password');
  });

  it('enforces the shared password length and UTF-8 byte limits', async () => {
    render(<Page />);
    const password = screen.getByLabelText('Set Account Password *');
    await userEvent.type(password, 'short');
    await userEvent.click(screen.getByRole('button', { name: 'Accept Invitation' }));
    expect(await screen.findByText('Password must be at least 8 characters.')).toBeInTheDocument();
    expect(mocks.accept).not.toHaveBeenCalled();

    await userEvent.clear(password);
    await userEvent.type(password, 'é'.repeat(36));
    await userEvent.type(password, 'a');
    await userEvent.click(screen.getByRole('button', { name: 'Accept Invitation' }));
    expect(await screen.findByText('Password must be at most 72 UTF-8 bytes.')).toBeInTheDocument();
    expect(mocks.accept).not.toHaveBeenCalled();
  });
});
