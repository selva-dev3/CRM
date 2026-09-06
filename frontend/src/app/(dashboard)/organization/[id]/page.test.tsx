import { render, screen, fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  useOrganizationByIdQuery: vi.fn(),
  useParams: vi.fn(),
  subscription: vi.fn(),
  cancel: vi.fn(),
  resume: vi.fn(),
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
  useOrganizationSubscriptionQuery: mocks.subscription,
  useCancelSubscriptionMutation: () => ({ mutateAsync: mocks.cancel, isPending: false }),
  useResumeSubscriptionMutation: () => ({ mutateAsync: mocks.resume, isPending: false }),
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
    mocks.subscription.mockReturnValue({ data: undefined });
    mocks.cancel.mockReset();
    mocks.resume.mockReset();
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

  function openBilling(data?: Record<string, unknown>, flags = {}) {
    mocks.subscription.mockReturnValue({ data, ...flags });
    render(<OrganizationDetail isCurrentOrgView />);
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Subscription & Billing' }), { button: 0, ctrlKey: false });
  }

  const activeSubscription = { plan: 'Enterprise', status: 'active', provider_linked: true, auto_renew: true, amount: 0, billing_cycle: 'Monthly' };

  it('shows safe cancellation errors from the backend', async () => {
    mocks.cancel.mockRejectedValue(new Error('Subscription billing credentials require administrator review.'));
    openBilling(activeSubscription);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel Subscription' }));
    expect(await screen.findByText('Subscription billing credentials require administrator review.')).toBeInTheDocument();
    expect(mocks.cancel).toHaveBeenCalledOnce();
    expect(screen.getByText('₹0/mo')).toBeInTheDocument();
  });

  it('shows scheduled cancellation and resumes renewal through the API', async () => {
    mocks.resume.mockResolvedValue({ message: 'Subscription renewal enabled' });
    openBilling({ ...activeSubscription, auto_renew: false });
    expect(screen.getByText('Cancels at period end')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel Subscription' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Resume Renewal' }));
    expect(await screen.findByText('Subscription renewal enabled')).toBeInTheDocument();
    expect(mocks.resume).toHaveBeenCalledOnce();
    expect(mocks.cancel).not.toHaveBeenCalled();
  });

  it.each([
    [{ ...activeSubscription, provider_linked: false }, {}, 'No Stripe subscription linked'],
    [{ ...activeSubscription, status: 'cancelled' }, {}, 'Cancelled'],
    [{ ...activeSubscription, status: 'past_due' }, {}, 'Payment overdue'],
    [undefined, { isLoading: true }, 'Loading billing status…'],
    [activeSubscription, { isError: true }, 'Billing status unavailable'],
    [undefined, {}, 'No subscription information'],
  ])('renders truthful billing status: %s', (data, flags, label) => {
    openBilling(data, flags);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText('Active Billing')).not.toBeInTheDocument();
    if (label !== 'Payment overdue') {
      expect(screen.queryByRole('button', { name: 'Cancel Subscription' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Resume Renewal' })).not.toBeInTheDocument();
    }
  });
});
