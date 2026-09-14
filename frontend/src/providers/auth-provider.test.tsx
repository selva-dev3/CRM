import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './auth-provider';
import type { CurrentUserResponse } from '@/lib/api/auth';
import { apiClient } from '@/lib/api/client';
import { getOrganizationContext, setOrganizationContext } from '@/lib/organization-context';
import { AUTH_SESSION_BROADCAST_KEY, setAccessToken } from '@/lib/auth-session';

const ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjIwMDAwMDAwMDB9.signature';

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
      <span>{auth.isLoggingOut ? 'logging-out' : 'idle'}</span>
      <button type="button" onClick={() => { setAccessToken(ACCESS_TOKEN); auth.setSession({ id: 'user-1', name: 'Alex', email: 'alex@crm.com', role: 'Admin', permissions: [] }, true); }}>Set session</button>
      <button type="button" onClick={() => void auth.logout().catch(() => undefined)}>Logout</button>
      <button type="button" onClick={() => void auth.verifySession().catch(() => undefined)}>Verify</button>
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

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('ignores an unavailable response from an organization that is no longer selected', async () => {
    const queryClient = new QueryClient();
    renderProvider(queryClient);
    await userEvent.click(screen.getByRole('button', { name: 'Set session' }));
    setOrganizationContext('new-organization');
    queryClient.setQueryData(['contacts'], [{ id: 'new-contact' }]);
    act(() => window.dispatchEvent(new CustomEvent('organization:unavailable', { detail: 'old-organization' })));
    expect(screen.getByText('authenticated')).toBeInTheDocument();
    expect(queryClient.getQueryData(['contacts'])).toEqual([{ id: 'new-contact' }]);
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

  it('restores authoritative user state with a persisted access token', async () => {
    setAccessToken(ACCESS_TOKEN);
    mocks.getCurrentUserApi.mockResolvedValue({
      id: 'user-1',
      name: 'Alex',
      email: 'alex@crm.com',
      role: 'Admin',
      permissions: ['contacts:read'],
    });
    renderProvider();

    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));

    expect(await screen.findByText('alex@crm.com')).toBeInTheDocument();
    expect(screen.getByText('authenticated')).toBeInTheDocument();
  });

  it('clears the previous account cache when a new session is installed', async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(['contacts'], [{ id: 'account-a-contact' }]);
    renderProvider(queryClient);

    await userEvent.click(screen.getByRole('button', { name: 'Set session' }));

    expect(queryClient.getQueryData(['contacts'])).toBeUndefined();
    expect(screen.getByText('alex@crm.com')).toBeInTheDocument();
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
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('clears stale organization context on a same-tab login event', async () => {
    renderProvider();
    setOrganizationContext('previous-organization');
    sessionStorage.setItem('user', JSON.stringify({
      id: 'invited-user', name: 'Invitee', email: 'invitee@crm.com', role: 'Admin',
      organization_id: 'new-organization', permissions: ['users:read'],
    }));
    setAccessToken(ACCESS_TOKEN);

    act(() => window.dispatchEvent(new CustomEvent('auth:session-changed', {
      detail: { action: 'login' },
    })));

    expect(await screen.findByText('invitee@crm.com')).toBeInTheDocument();
    expect(getOrganizationContext()).toBeNull();
  });

  it('clears cached tenant data after an authoritative permission refresh', async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(['contacts'], [{ id: 'contact-1' }]);
    mocks.getCurrentUserApi.mockResolvedValue({
      id: 'user-1',
      name: 'Alex',
      email: 'alex@crm.com',
      role: 'Read Only',
      permissions: ['contacts:read'],
    });
    setAccessToken(ACCESS_TOKEN);
    renderProvider(queryClient);

    act(() => window.dispatchEvent(new CustomEvent('auth:session-changed', {
      detail: { action: 'refresh' },
    })));

    expect(await screen.findByText('alex@crm.com')).toBeInTheDocument();
    await waitFor(() => expect(queryClient.getQueryData(['contacts'])).toBeUndefined());
  });

  it('does not treat an ordinary profile verification as a new login session', async () => {
    let releaseRequest: ((response: object) => void) | undefined;
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise<object>((resolve) => {
      releaseRequest = resolve;
    })));
    mocks.getCurrentUserApi.mockResolvedValue({
      id: 'user-1',
      name: 'Updated Alex',
      email: 'alex@crm.com',
      role: 'Admin',
      permissions: [],
    });
    renderProvider();
    await userEvent.click(screen.getByRole('button', { name: 'Set session' }));

    const pendingRequest = apiClient.get('/contacts');
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
    expect(await screen.findByText('alex@crm.com')).toBeInTheDocument();
    releaseRequest?.({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue([{ id: 'current-session-contact' }]),
    });

    await expect(pendingRequest).resolves.toEqual([{ id: 'current-session-contact' }]);
  });

  it('clears local state when backend logout fails', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    queryClient.setQueryData(['contacts'], [{ id: 'contact-1' }]);
    mocks.logoutApi.mockRejectedValue(new Error('Network unavailable'));
    renderProvider(queryClient);
    await user.click(screen.getByRole('button', { name: 'Set session' }));
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => expect(screen.getByText('unauthenticated')).toBeInTheDocument());
    expect(queryClient.getQueryData(['contacts'])).toBeUndefined();
    expect(sessionStorage.getItem('user')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('clears only the current user pending session operations on logout', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('pending-invoice-payment:user-1:invoice-1', '{}');
    sessionStorage.setItem('subscription-checkout:user-1:org-1', '{}');
    sessionStorage.setItem('pending-invoice-payment:user-2:invoice-2', '{}');
    sessionStorage.setItem('unrelated-session-state', 'keep');
    renderProvider();

    await user.click(screen.getByRole('button', { name: 'Set session' }));
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(sessionStorage.getItem('pending-invoice-payment:user-1:invoice-1')).toBeNull();
    expect(sessionStorage.getItem('subscription-checkout:user-1:org-1')).toBeNull();
    expect(sessionStorage.getItem('pending-invoice-payment:user-2:invoice-2')).toBe('{}');
    expect(sessionStorage.getItem('unrelated-session-state')).toBe('keep');
  });

  it('shares one logout operation across duplicate calls', async () => {
    let releaseLogout: (() => void) | undefined;
    mocks.logoutApi.mockReturnValue(new Promise<void>((resolve) => {
      releaseLogout = resolve;
    }));
    renderProvider();
    await userEvent.click(screen.getByRole('button', { name: 'Set session' }));

    const logoutButton = screen.getByRole('button', { name: 'Logout' });
    await userEvent.click(logoutButton);
    await waitFor(() => expect(screen.getByText('logging-out')).toBeInTheDocument());
    await userEvent.click(logoutButton);
    expect(mocks.logoutApi).toHaveBeenCalledOnce();

    releaseLogout?.();
    await waitFor(() => expect(screen.getByText('idle')).toBeInTheDocument());
  });

  it('does not restore a session from verification that started before logout', async () => {
    let releaseVerification: ((user: CurrentUserResponse) => void) | undefined;
    mocks.getCurrentUserApi.mockReturnValue(new Promise((resolve) => {
      releaseVerification = resolve;
    }));
    renderProvider();
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
    await userEvent.click(screen.getByRole('button', { name: 'Logout' }));

    releaseVerification?.({ id: 'user-1', name: 'Alex', email: 'alex@crm.com', role: 'Admin', permissions: [] });
    await waitFor(() => expect(screen.getByText('unauthenticated')).toBeInTheDocument());
    expect(screen.getByText('no-user')).toBeInTheDocument();
  });
});
