import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import UserDetailPage from './page';

const routeUserId = 'dfd38bda-e378-4d3b-8485-7fd651741378';
const organizationId = 'ff39188-e8e4-42db-8563-6e9ed72d9dc1';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: routeUserId }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/components/common/permission-gate', () => ({
  PermissionGate: ({ children }: { children: ReactNode }) => children,
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({
    data: { id: organizationId, name: 'My CRM' },
  }),
}));

vi.mock('@/lib/api/users', () => {
  const mutation = () => ({ isPending: false, mutateAsync: vi.fn() });
  return {
    useUserQuery: () => ({
      data: {
        id: routeUserId,
        name: 'Selvakumar',
        email: 'selvakumar@example.com',
        role: 'Sales Manager',
        organization_id: organizationId,
        is_active: true,
        created_at: '2026-09-04T07:09:48Z',
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }),
    useUserQuotaQuery: () => ({
      data: { user_id: routeUserId, target_amount: null, achieved_amount: 0 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }),
    useUserPerformanceQuery: () => ({
      data: { user_id: routeUserId, win_rate: 0, avg_deal_size: 0, calls_made: 0 },
      isLoading: false,
      isError: false,
    }),
    useUserPermissionsQuery: () => ({
      data: { user_id: routeUserId, permissions: [] },
      isLoading: false,
      isError: false,
    }),
    useUserActivitiesQuery: () => ({ data: [], isLoading: false, isError: false }),
    useUserTeamsQuery: () => ({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }),
    useActivateUserMutation: mutation,
    useDeactivateUserMutation: mutation,
    useDeleteUserMutation: mutation,
    useResetUserPasswordAdminMutation: mutation,
    useAssignUserTeamMutation: mutation,
    useRemoveUserTeamMutation: mutation,
    useSetUserQuotaMutation: mutation,
  };
});

describe('UserDetailPage', () => {
  it('renders API values and does not expose IDs or fabricated detail data', () => {
    const { container } = render(<UserDetailPage />);

    expect(screen.getAllByText('Selvakumar').length).toBeGreaterThan(0);
    expect(screen.getByText('Sales Manager')).toBeInTheDocument();
    expect(screen.getByText('My CRM')).toBeInTheDocument();
    expect(screen.getByText('Not configured')).toBeInTheDocument();
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText('$0')).toBeInTheDocument();
    expect(screen.getByText('No assigned teams')).toBeInTheDocument();

    expect(container).not.toHaveTextContent(routeUserId);
    expect(container).not.toHaveTextContent(organizationId);
    expect(container).not.toHaveTextContent('$125,000');
    expect(container).not.toHaveTextContent('68.5%');
    expect(container).not.toHaveTextContent('Enterprise Sales East');
    expect(container).not.toHaveTextContent('Global Account Executives');
  });
});
