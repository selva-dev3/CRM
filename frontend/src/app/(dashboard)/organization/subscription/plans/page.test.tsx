import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SubscriptionPlansPage from './page';

const mockPush = vi.fn();
const mockBack = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    back: mockBack,
  }),
  useSearchParams: () => ({
    get: vi.fn().mockImplementation((param: string) => {
      if (param === 'org_id') return 'org-123';
      return null;
    }),
  }),
}));

const mockPlansData = [
  {
    id: 'plan-free',
    name: 'Free',
    slug: 'free',
    price_monthly: 0,
    price_yearly: 0,
    max_users: 3,
    max_storage_gb: 5,
    ai_credits: 50,
    features: ['Dashboard', 'Leads', 'Contacts'],
    is_active: true,
  },
  {
    id: 'plan-starter',
    name: 'Starter',
    slug: 'starter',
    price_monthly: 999,
    price_yearly: 9990,
    max_users: 10,
    max_storage_gb: 20,
    ai_credits: 500,
    features: ['Everything in Free', 'Deals', 'Tasks'],
    is_active: true,
  },
  {
    id: 'plan-professional',
    name: 'Professional',
    slug: 'professional',
    price_monthly: 2999,
    price_yearly: 29990,
    max_users: 50,
    max_storage_gb: 100,
    ai_credits: 5000,
    features: ['Everything in Starter', 'AI', 'Reports'],
    is_active: true,
  },
  {
    id: 'plan-business',
    name: 'Business',
    slug: 'business',
    price_monthly: 6999,
    price_yearly: 69990,
    max_users: 200,
    max_storage_gb: 500,
    ai_credits: 20000,
    features: ['Everything in Professional'],
    is_active: true,
  },
  {
    id: 'plan-enterprise',
    name: 'Enterprise',
    slug: 'enterprise',
    price_monthly: 29990,
    price_yearly: 299900,
    max_users: 100,
    max_storage_gb: 500,
    ai_credits: 100000,
    features: ['Unlimited Everything', 'Priority Support'],
    is_active: true,
  },
];

const mockUseSubscriptionPlansQuery = vi.fn();
const mockUseOrganizationSubscriptionQuery = vi.fn();
const mockMutateAsync = vi.fn();
const mockUseCreateSubscriptionCheckoutMutation = vi.fn();

vi.mock('@/lib/api/organizations', () => ({
  useSubscriptionPlansQuery: () => mockUseSubscriptionPlansQuery(),
  useOrganizationSubscriptionQuery: () => mockUseOrganizationSubscriptionQuery(),
  useCreateSubscriptionCheckoutMutation: () => mockUseCreateSubscriptionCheckoutMutation(),
  createSubscriptionCheckoutApi: vi.fn(),
  upgradeOrganizationSubscriptionApi: vi.fn(),
  getSubscriptionPlansApi: vi.fn(),
  getOrganizationSubscriptionApi: vi.fn(),
}));

describe('SubscriptionPlansPage - Stripe Checkout Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMutateAsync.mockResolvedValue({
      checkout_url: 'https://checkout.stripe.com/pay/cs_test_mock_session',
      session_id: 'cs_test_mock_session',
      status: 'success',
    });
    mockUseCreateSubscriptionCheckoutMutation.mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
    });
    mockUseOrganizationSubscriptionQuery.mockReturnValue({
      data: { plan: 'Free', billing_cycle: 'Monthly', amount: 0 },
    });
    mockUseSubscriptionPlansQuery.mockReturnValue({
      data: mockPlansData,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it('renders loading state when fetching plans', () => {
    mockUseSubscriptionPlansQuery.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SubscriptionPlansPage />);
    expect(screen.getByText(/Loading available subscription plans/i)).toBeInTheDocument();
  });

  it('renders error state when plans query fails with retry button', () => {
    const mockRefetch = vi.fn();
    mockUseSubscriptionPlansQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
      refetch: mockRefetch,
    });

    render(<SubscriptionPlansPage />);
    expect(screen.getByText('Failed to Load Plans')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry Loading Plans/i });
    fireEvent.click(retryBtn);
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('renders all active plans with server-side prices and quotas', () => {
    render(<SubscriptionPlansPage />);

    expect(screen.getByText('Free')).toBeInTheDocument();
    expect(screen.getByText('Starter')).toBeInTheDocument();
    expect(screen.getByText('Professional')).toBeInTheDocument();
    expect(screen.getByText('Business')).toBeInTheDocument();
    expect(screen.getByText('Enterprise')).toBeInTheDocument();

    expect(screen.getByText('₹0')).toBeInTheDocument();
    expect(screen.getByText('₹999')).toBeInTheDocument();
    expect(screen.getByText('₹2,999')).toBeInTheDocument();
    expect(screen.getByText('₹6,999')).toBeInTheDocument();
    expect(screen.getByText('₹29,990')).toBeInTheDocument();

    expect(screen.getByText('Current Plan')).toBeInTheDocument();
  });

  it('calls checkout mutation with plan_slug and org_id when user clicks upgrade', async () => {
    render(<SubscriptionPlansPage />);

    // Upgrade button should be disabled initially until a plan is selected
    const upgradeButton = screen.getByRole('button', { name: /Select a Plan/i });
    expect(upgradeButton).toBeDisabled();

    // Click Starter plan card
    const starterButton = screen.getByRole('button', { name: /Choose Starter/i });
    fireEvent.click(starterButton);

    // Upgrade button should now be enabled with "Upgrade to Starter"
    const activeUpgradeButton = screen.getByRole('button', { name: /Upgrade to Starter/i });
    expect(activeUpgradeButton).toBeEnabled();

    // Click Upgrade to trigger checkout
    fireEvent.click(activeUpgradeButton);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        plan_slug: 'starter',
        org_id: 'org-123',
      });
    });
  });

  it('handles checkout creation failure without navigating away', async () => {
    mockMutateAsync.mockRejectedValueOnce({
      response: { data: { message: 'Stripe gateway unavailable' } },
    });

    render(<SubscriptionPlansPage />);

    const starterButton = screen.getByRole('button', { name: /Choose Starter/i });
    fireEvent.click(starterButton);

    const upgradeButton = screen.getByRole('button', { name: /Upgrade to Starter/i });
    fireEvent.click(upgradeButton);

    expect(await screen.findByText('Stripe gateway unavailable')).toBeInTheDocument();
    expect(upgradeButton).toBeEnabled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('navigates back to organization details on cancel / back click', () => {
    render(<SubscriptionPlansPage />);

    const backButton = screen.getByText(/Back to Organization & Billing/i);
    fireEvent.click(backButton);

    expect(mockPush).toHaveBeenCalledWith('/organization/org-123');
  });
});
