import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import Page from './page';
import type { SubscriptionCheckoutOperation } from '@/lib/api/subscription-checkout';
import type { SubscriptionPlanItem } from '@/lib/api/organizations';

const plans: SubscriptionPlanItem[] = [
  {
    id: 'plan-free', name: 'Free', slug: 'free', description: 'Free description',
    price_monthly: 0, price_yearly: 0, currency: 'INR', billing_cycle: 'month',
    max_users: 3, max_storage_gb: 5, ai_credits: 50, features: ['Dashboard'],
    is_popular: false, is_active: true, sort_order: 1,
  },
  {
    id: 'plan-starter', name: 'Starter', slug: 'starter', description: 'Starter description',
    price_monthly: 999, price_yearly: 9990, currency: 'INR', billing_cycle: 'month',
    max_users: 10, max_storage_gb: 20, ai_credits: 500, features: ['Deals'],
    is_popular: false, is_active: true, sort_order: 2,
  },
  {
    id: 'plan-professional', name: 'Professional', slug: 'professional', description: 'Professional description',
    price_monthly: 2999, price_yearly: 29990, currency: 'INR', billing_cycle: 'month',
    max_users: 50, max_storage_gb: 100, ai_credits: 5000, features: ['Reports'],
    is_popular: true, is_active: true, sort_order: 3,
  },
  {
    id: 'plan-business', name: 'Business', slug: 'business', description: 'Business description',
    price_monthly: 6999, price_yearly: 69990, currency: 'INR', billing_cycle: 'month',
    max_users: 200, max_storage_gb: 500, ai_credits: 20000, features: ['Automation'],
    is_popular: false, is_active: true, sort_order: 4,
  },
  {
    id: 'plan-enterprise', name: 'Enterprise', slug: 'enterprise', description: 'Enterprise description',
    price_monthly: 29990, price_yearly: 299900, currency: 'INR', billing_cycle: 'month',
    max_users: 100, max_storage_gb: 500, ai_credits: 100000, features: ['Priority support'],
    is_popular: false, is_active: true, sort_order: 5,
  },
];

const mocks = vi.hoisted(() => ({
  start: vi.fn(), pending: false, permission: true, error: null as string | null,
  empty: false, apiError: false, currentPlan: 'Free', providerLinked: false,
  operation: null as SubscriptionCheckoutOperation | null,
}));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock('@/lib/api/organizations', () => ({
  useOrganizationSubscriptionQuery: () => ({
    data: { plan: mocks.currentPlan, provider_linked: mocks.providerLinked, status: 'active' },
    isLoading: false,
    isError: false,
  }),
  useSubscriptionPlansQuery: () => ({
    data: mocks.empty ? [] : plans,
    isLoading: false,
    isError: mocks.apiError,
    error: mocks.apiError ? new Error('Catalog unavailable') : null,
    refetch: vi.fn(),
  }),
}));
vi.mock('@/lib/api/subscription-checkout', () => ({
  useSubscriptionCheckout: () => ({
    start: mocks.start, ready: true, isPending: mocks.pending, error: mocks.error,
    operation: mocks.operation, isCurrentOrganization: true, requiresAdministratorReview: false,
  }),
}));
vi.mock('@/hooks/use-has-permission', () => ({ useHasPermission: () => ({ hasPermission: () => mocks.permission }) }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.pending = false;
  mocks.permission = true;
  mocks.error = null;
  mocks.empty = false;
  mocks.apiError = false;
  mocks.currentPlan = 'Free';
  mocks.providerLinked = false;
  mocks.operation = null;
});

it('keeps current plan and latest selected plan independent', () => {
  render(<Page />);
  expect(screen.getByRole('button', { name: 'Active Plan' })).toBeDisabled();

  fireEvent.click(screen.getByRole('button', { name: 'Choose Starter' }));
  expect(screen.getByText(/Selected Tier:/)).toHaveTextContent('Starter');

  fireEvent.click(screen.getByRole('button', { name: 'Choose Professional' }));
  expect(screen.getByText(/Selected Tier:/)).toHaveTextContent('Professional');
  expect(screen.getAllByText('Selected')).toHaveLength(2);
  expect(screen.getByRole('button', { name: 'Choose Starter' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Active Plan' })).toBeDisabled();
});

it('allows selecting every tier and keeps only the latest card selected', () => {
  mocks.currentPlan = 'Legacy';
  render(<Page />);

  for (const plan of plans) {
    fireEvent.click(screen.getByRole('button', { name: `Choose ${plan.name}` }));
    expect(screen.getByText(/Selected Tier:/)).toHaveTextContent(plan.name);
  }

  expect(screen.getAllByText('Selected')).toHaveLength(2);
  expect(screen.getByRole('button', { name: 'Selected' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Choose Business' })).toBeInTheDocument();
});

it('starts checkout with the latest selected backend plan slug', () => {
  render(<Page />);
  fireEvent.click(screen.getByRole('button', { name: 'Choose Starter' }));
  fireEvent.click(screen.getByRole('button', { name: 'Choose Professional' }));
  fireEvent.click(screen.getByRole('button', { name: 'Start subscription with Stripe' }));
  expect(mocks.start).toHaveBeenCalledWith('professional');
});

it('renders price, terms, limits, features, and popular state from API data', () => {
  render(<Page />);
  expect(screen.getByText('Professional description')).toBeInTheDocument();
  expect(screen.getByText('5,000')).toBeInTheDocument();
  expect(screen.getByText('Reports')).toBeInTheDocument();
  expect(screen.getByText('Popular')).toBeInTheDocument();
  expect(screen.getAllByText('/ month').length).toBeGreaterThan(0);
  expect(screen.queryByText(/Plans are billed monthly in INR/)).not.toBeInTheDocument();
});

it('disables selection only while an actual submission is in progress', () => {
  mocks.pending = true;
  render(<Page />);
  expect(screen.getByRole('button', { name: 'Opening Stripe…' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Choose Starter' })).toBeDisabled();
});

it('allows changing UI selection while preserving a different pending operation', () => {
  mocks.operation = {
    payload: { plan_slug: 'starter' },
    idempotencyKey: 'c666f2cf-59ad-47a9-80ef-1327d1229b91',
  };
  render(<Page />);
  fireEvent.click(screen.getByRole('button', { name: 'Choose Professional' }));
  expect(screen.getByText(/Selected Tier:/)).toHaveTextContent('Professional');
  expect(screen.getByRole('button', { name: 'Resolve pending checkout first' })).toBeDisabled();
  expect(screen.getByRole('link', { name: 'Check subscription status' })).toHaveAttribute(
    'href', '/organization/subscription/payment/success?plan_slug=starter',
  );
});

it('requires billing permission', () => {
  mocks.permission = false;
  render(<Page />);
  fireEvent.click(screen.getByRole('button', { name: 'Choose Starter' }));
  expect(screen.getByRole('button', { name: 'Start subscription with Stripe' })).toBeDisabled();
});

it('shows API errors without rendering a fake plan catalog', () => {
  mocks.apiError = true;
  render(<Page />);
  expect(screen.getByText('Failed to Load Plans')).toBeInTheDocument();
  expect(screen.queryByText('Starter description')).not.toBeInTheDocument();
});

it('shows an empty state when the database returns no active plans', () => {
  mocks.empty = true;
  render(<Page />);
  expect(screen.getByText('No subscription plans are available.')).toBeInTheDocument();
});
