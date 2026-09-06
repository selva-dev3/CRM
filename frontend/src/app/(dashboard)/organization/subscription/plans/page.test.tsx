import { render, screen, fireEvent } from '@testing-library/react';
import { vi, it, expect, beforeEach } from 'vitest';
import Page from './page';
import type { SubscriptionCheckoutOperation } from '@/lib/api/subscription-checkout';

const mocks = vi.hoisted(() => ({ start: vi.fn(), pending: false, permission: true, error: null as string | null, empty: false, currentPlan: 'Basic', operation: null as SubscriptionCheckoutOperation | null }));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock('@/lib/api/organizations', () => ({
  useOrganizationSubscriptionQuery: () => ({ data: { plan: mocks.currentPlan } }),
  useSubscriptionPlansQuery: () => ({ data: mocks.empty ? [] : [{ slug: 'pro', name: 'Pro', price_monthly: 100, price_yearly: 1000, max_users: 10, max_storage_gb: 10, ai_credits: 100, features: [] }] }),
}));
vi.mock('@/lib/api/subscription-checkout', () => ({ useSubscriptionCheckout: () => ({ start: mocks.start, ready: true, isPending: mocks.pending, error: mocks.error, operation: mocks.operation, isCurrentOrganization: true }) }));
vi.mock('@/hooks/use-has-permission', () => ({ useHasPermission: () => ({ hasPermission: () => mocks.permission }) }));
beforeEach(() => { vi.clearAllMocks(); mocks.pending = false; mocks.permission = true; mocks.error = null; mocks.empty = false; mocks.currentPlan = 'Basic'; mocks.operation = null; });
it('starts Stripe subscription checkout for the selected plan', () => {
  render(<Page />);
  expect(screen.getByRole('button', { name: 'Continue with Stripe' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Choose Pro' }));
  fireEvent.click(screen.getByRole('button', { name: 'Continue with Stripe' }));
  expect(mocks.start).toHaveBeenCalledWith('pro');
  expect(screen.getByText(/Plans are billed monthly in INR/)).toBeInTheDocument();
  expect(screen.queryByText(/billed yearly/i)).not.toBeInTheDocument();
});
it('disables submission while opening Stripe', () => {
  mocks.pending = true;
  render(<Page />);
  expect(screen.getByRole('button', { name: 'Opening Stripe…' })).toBeDisabled();
});
it('requires billing permission', () => {
  mocks.permission = false;
  render(<Page />);
  fireEvent.click(screen.getByRole('button', { name: 'Choose Pro' }));
  expect(screen.getByRole('button', { name: 'Continue with Stripe' })).toBeDisabled();
});
it('shows errors and empty plans', () => {
  mocks.error = 'Billing unavailable'; mocks.empty = true;
  render(<Page />);
  expect(screen.getByRole('alert')).toHaveTextContent('Billing unavailable');
  expect(screen.getByText('No subscription plans are available.')).toBeInTheDocument();
});
it.each([null, 'Idempotency fingerprint conflict'])('offers verification for a pending current-plan request with error %s', (error) => {
  mocks.currentPlan = 'Pro';
  mocks.operation = { payload: { plan_slug: 'pro' }, idempotencyKey: 'c666f2cf-59ad-47a9-80ef-1327d1229b91' };
  mocks.error = error;
  render(<Page />);
  expect(screen.getByRole('link', { name: 'Check subscription status' })).toHaveAttribute('href', '/organization/subscription/payment/success?plan_slug=pro');
  expect(screen.getByRole('button', { name: 'Retry subscription request' })).not.toBeDisabled();
  expect(screen.getByText(/Activation requires server verification/)).toBeInTheDocument();
  expect(mocks.start).not.toHaveBeenCalled();
});
it('keeps verification accessible while a request is pending and the plan list is empty', () => {
  mocks.pending = true; mocks.empty = true;
  mocks.operation = { payload: { plan_slug: 'pro&other=value' }, idempotencyKey: 'c666f2cf-59ad-47a9-80ef-1327d1229b91' };
  render(<Page />);
  expect(screen.getByRole('link', { name: 'Check subscription status' })).toHaveAttribute('href', '/organization/subscription/payment/success?plan_slug=pro%26other%3Dvalue');
});
