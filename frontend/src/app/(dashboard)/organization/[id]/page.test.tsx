import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  useOrganizationByIdQuery: vi.fn(),
  useParams: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useParams: mocks.useParams,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({
    data: {
      id: 'org-current',
      name: 'Current CRM',
      domain: 'current.crm.test',
      plan: 'Enterprise',
      max_users: 100,
      status: 'active',
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useOrganizationByIdQuery: mocks.useOrganizationByIdQuery,
  useUpdateOrganizationMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOrganizationMembersQuery: () => ({ data: [], refetch: vi.fn() }),
  useRemoveOrganizationMemberMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOrganizationSubscriptionQuery: () => ({ data: undefined, refetch: vi.fn() }),
  useCancelSubscriptionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOrganizationUsageQuery: () => ({ data: undefined }),
  useUpdateBrandingMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVerifyDomainMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOrganizationDomainsQuery: () => ({ data: [], refetch: vi.fn() }),
  useOrganizationAuditLogsQuery: () => ({ data: [] }),
  useTransferOwnershipMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import OrganizationDetailPage from './page';
import OrganizationDetail from '@/components/features/organization/OrganizationDetail';

describe('Organization detail route and current organization mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useParams.mockReturnValue({});
    mocks.useOrganizationByIdQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
  });

  it('uses current organization data without enabling a by-id request', () => {
    render(<OrganizationDetail isCurrentOrgView />);

    expect(mocks.useOrganizationByIdQuery).toHaveBeenCalledWith('', false);
    expect(screen.getByDisplayValue('Current CRM')).toBeInTheDocument();
  });

  it('renders the by-ID route without custom page props', () => {
    mocks.useParams.mockReturnValue({ id: 'org-selected' });
    mocks.useOrganizationByIdQuery.mockReturnValue({
      data: { id: 'org-selected', name: 'Selected CRM', plan: 'Enterprise', status: 'active' },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<OrganizationDetailPage />);

    expect(mocks.useOrganizationByIdQuery).toHaveBeenCalledWith('org-selected', true);
    expect(screen.getByDisplayValue('Selected CRM')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Current CRM')).not.toBeInTheDocument();
  });
});
