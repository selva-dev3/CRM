import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardLayout from './layout';

const { routerPush, getCurrentUserApi } = vi.hoisted(() => ({
  routerPush: vi.fn(),
  getCurrentUserApi: vi.fn(),
}));

vi.mock('next/link', () => ({
  default: ({ children, ...props }: React.ComponentProps<'a'>) => <a {...props}>{children}</a>,
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard',
  useRouter: () => ({ push: routerPush }),
}));

vi.mock('@/lib/api', () => ({
  getCurrentUserApi,
  logoutApi: vi.fn(),
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({ data: { name: 'Acme Corporation' } }),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  notifyAuthUserChanged: vi.fn(),
  useHasPermission: () => ({ permissions: ['all'], hasPermission: () => true }),
}));

vi.mock('@/components/features/ai/ai-chat-assistant', () => ({
  AIChatAssistant: () => null,
}));

vi.mock('@/components/features/notifications/notification-bell', () => ({
  NotificationBell: () => null,
}));

vi.mock('@/components/common/global-search-modal', () => ({
  GlobalSearchModal: () => null,
}));

describe('DashboardLayout', () => {
  beforeEach(() => {
    getCurrentUserApi.mockReset();
    routerPush.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it('shows the loading state before authentication resolves', () => {
    getCurrentUserApi.mockReturnValue(new Promise(() => {}));
    render(<DashboardLayout>Page content</DashboardLayout>);

    expect(screen.getByText('Verifying Session Token...')).toBeInTheDocument();
  });

  it('renders authenticated user and organization data after authentication succeeds', async () => {
    getCurrentUserApi.mockResolvedValue({ name: 'Jane Doe', email: 'jane@example.com', role: 'Manager' });
    render(<DashboardLayout>Page content</DashboardLayout>);

    expect(await screen.findByText('Page content')).toBeInTheDocument();
    expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
    expect(screen.getByText('Role: Manager')).toBeInTheDocument();
    expect(sessionStorage.getItem('user')).toContain('Jane Doe');
  });

  it('redirects to login when authentication fails', async () => {
    getCurrentUserApi.mockRejectedValue(new Error('Unauthenticated'));
    render(<DashboardLayout>Page content</DashboardLayout>);

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith('/login'));
    expect(screen.queryByText('Page content')).not.toBeInTheDocument();
  });

  it('closes the mobile menu when a navigation link is clicked', async () => {
    const user = userEvent.setup();
    getCurrentUserApi.mockResolvedValue({ name: 'Jane Doe', email: 'jane@example.com', role: 'Manager' });
    const { container } = render(<DashboardLayout>Page content</DashboardLayout>);
    await screen.findByText('Page content');

    const menuButton = container.querySelector('header button');
    expect(menuButton).toBeTruthy();
    await user.click(menuButton as HTMLButtonElement);
    const navigation = screen.getByRole('dialog', { name: 'CRM navigation' });
    expect(navigation).toBeInTheDocument();

    await user.click(within(navigation).getByRole('link', { name: 'Leads' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'CRM navigation' })).not.toBeInTheDocument();
    });
  });
});
