import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './auth-provider';
import { AUTH_SESSION_BROADCAST_KEY } from '@/lib/auth-session';

const mocks = vi.hoisted(() => ({
  getCurrentUserApi: vi.fn(),
  logoutApi: vi.fn(),
}));

vi.mock('@/lib/api/auth', () => ({
  getCurrentUserApi: mocks.getCurrentUserApi,
  logoutApi: mocks.logoutApi,
}));

function Consumer() {
  const auth = useAuth();
  return (
    <div>
      <span>{auth.status}</span>
      <span>{auth.user?.email ?? 'no-user'}</span>
      <button type="button" onClick={() => auth.setSession({ id: 'user-1', name: 'Alex', email: 'alex@crm.com', role: 'Admin', permissions: [] }, true)}>Set session</button>
      <button type="button" onClick={() => void auth.logout().catch(() => undefined)}>Logout</button>
    </div>
  );
}

function renderProvider(queryClient = new QueryClient()) {
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider><Consumer /></AuthProvider>
      </QueryClientProvider>,
    ),
  };
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    mocks.logoutApi.mockResolvedValue(undefined);
  });

  it('clears protected query data after a successful logout', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    queryClient.setQueryData(['contacts'], [{ id: 'contact-1' }]);
    renderProvider(queryClient);

    await user.click(screen.getByRole('button', { name: 'Set session' }));
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => expect(screen.getByText('unauthenticated')).toBeInTheDocument());
    expect(queryClient.getQueryData(['contacts'])).toBeUndefined();
    expect(localStorage.getItem('user')).toBeNull();
    expect(sessionStorage.getItem('user')).toBeNull();
  });

  it('reacts immediately to logout from another browser tab', async () => {
    renderProvider();
    await userEvent.click(screen.getByRole('button', { name: 'Set session' }));
    localStorage.removeItem('user');
    sessionStorage.removeItem('user');

    act(() => {
      window.dispatchEvent(new StorageEvent('storage', {
        key: AUTH_SESSION_BROADCAST_KEY,
        newValue: JSON.stringify({ action: 'logout', timestamp: Date.now() }),
      }));
    });

    expect(await screen.findByText('unauthenticated')).toBeInTheDocument();
    expect(screen.getByText('no-user')).toBeInTheDocument();
  });

  it('does not clear local state when backend logout fails', async () => {
    const user = userEvent.setup();
    mocks.logoutApi.mockRejectedValue(new Error('Network unavailable'));
    renderProvider();
    await user.click(screen.getByRole('button', { name: 'Set session' }));
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(screen.getByText('authenticated')).toBeInTheDocument();
    expect(sessionStorage.getItem('user')).toContain('alex@crm.com');
  });
});
