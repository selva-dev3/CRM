import { render, screen, fireEvent, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  useOrganizationByIdQuery: vi.fn(),
  useParams: vi.fn(),
  subscription: vi.fn(),
  cancel: vi.fn(),
  resume: vi.fn(),
  permissions: new Set<string>(['*']),
  members: vi.fn(),
  usage: vi.fn(),
  domains: vi.fn(),
  audit: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useParams: mocks.useParams,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({
    hasPermission: (permission: string) => mocks.permissions.has('*') || mocks.permissions.has(permission),
  }),
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
  useOrganizationMembersQuery: (...args: unknown[]) => mocks.members(...args),
  useRemoveOrganizationMemberMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOrganizationSubscriptionQuery: mocks.subscription,
  useCancelSubscriptionMutation: () => ({ mutateAsync: mocks.cancel, isPending: false }),
  useResumeSubscriptionMutation: () => ({ mutateAsync: mocks.resume, isPending: false }),
  useOrganizationUsageQuery: (...args: unknown[]) => mocks.usage(...args),
  useUpdateBrandingMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVerifyDomainMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOrganizationDomainsQuery: (...args: unknown[]) => mocks.domains(...args),
  useOrganizationAuditLogsQuery: (...args: unknown[]) => mocks.audit(...args),
  useTransferOwnershipMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import OrganizationDetailPage from './page';
import OrganizationDetail from '@/components/features/organization/OrganizationDetail';

describe('Organization detail route and current organization mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useParams.mockReturnValue({});
    mocks.permissions.clear();
    mocks.permissions.add('*');
    mocks.members.mockReturnValue({ data: [], refetch: vi.fn() });
    mocks.usage.mockReturnValue({ data: undefined });
    mocks.domains.mockReturnValue({ data: [], refetch: vi.fn() });
    mocks.audit.mockReturnValue({ data: [] });
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

  it('does not query or render privileged sections with organization read only', () => {
    mocks.permissions.clear();
    mocks.permissions.add('organization:read');

    render(<OrganizationDetail isCurrentOrgView />);

    expect(mocks.members).toHaveBeenCalledWith(false);
    expect(mocks.subscription).toHaveBeenCalledWith(false);
    expect(mocks.usage).toHaveBeenCalledWith(false);
    expect(mocks.domains).toHaveBeenCalledWith(false);
    expect(mocks.audit).toHaveBeenCalledWith(false);
    expect(screen.queryByRole('tab', { name: 'Members & Team' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Subscription & Billing' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save Profile' })).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('Current CRM')).toBeDisabled();
  });

  function openBilling(data?: Record<string, unknown>, flags = {}) {
    mocks.subscription.mockReturnValue({ data, ...flags });
    render(<OrganizationDetail isCurrentOrgView />);
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Subscription & Billing' }), { button: 0, ctrlKey: false });
  }

  const activeSubscription = { plan: 'Enterprise', status: 'active', provider_linked: true, auto_renew: true, amount: 0, currency: 'INR', billing_cycle: 'Monthly' };

  it('shows safe cancellation errors from the backend', async () => {
    mocks.cancel.mockRejectedValue(new Error('Subscription billing credentials require administrator review.'));
    openBilling(activeSubscription);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel Subscription' }));
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancel Subscription' }));
    expect(await screen.findByText('Subscription billing credentials require administrator review.')).toBeInTheDocument();
    expect(mocks.cancel).toHaveBeenCalledOnce();
    expect(screen.getByText('₹0')).toBeInTheDocument();
  });

  it('shows scheduled cancellation and resumes renewal through the API', async () => {
    mocks.resume.mockResolvedValue({ message: 'Subscription renewal enabled' });
    openBilling({ ...activeSubscription, auto_renew: false });
    expect(screen.getByText('Cancels at period end')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel Subscription' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Resume Renewal' }));
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Resume Renewal' }));
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
