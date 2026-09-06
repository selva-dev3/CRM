import { render, screen, fireEvent } from '@testing-library/react';
import { it, expect, vi, beforeEach } from 'vitest';
import Page from './page';
const mocks = vi.hoisted(() => ({ params: 'plan_slug=pro', complete: false, polling: true, isError: false, refetch: vi.fn(), hook: vi.fn() }));
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(mocks.params) }));
vi.mock('@/lib/api/subscription-checkout', () => ({ useSubscriptionVerification: (sessionId: string | null, planSlug: string | null) => {
  mocks.hook(sessionId, planSlug);
  return { complete: mocks.complete, polling: mocks.polling, isError: mocks.isError, error: new Error('Status unavailable'), refetch: mocks.refetch, data: { plan: 'Pro', message: 'Awaiting webhook' } };
} }));
beforeEach(() => { vi.clearAllMocks(); mocks.params = 'plan_slug=pro'; mocks.complete = false; mocks.polling = true; mocks.isError = false; });
it('verifies portal returns using the target plan without a session', () => {
  render(<Page />);
  expect(mocks.hook).toHaveBeenCalledWith(null, 'pro');
  expect(screen.getByText('Waiting for billing synchronization…')).toBeInTheDocument();
  expect(screen.queryByText('Subscription updated')).not.toBeInTheDocument();
});
it('passes the initial checkout session and plan to verification', () => {
  mocks.params = 'plan_slug=pro&session_id=cs_123';
  render(<Page />);
  expect(mocks.hook).toHaveBeenCalledWith('cs_123', 'pro');
});
it('shows success only after server verification completes', () => {
  mocks.complete = true;
  render(<Page />);
  expect(screen.getByRole('heading')).toHaveTextContent('Subscription updated');
});
it('offers a read-only check after polling expires', () => {
  mocks.polling = false;
  render(<Page />);
  expect(screen.getByText('Subscription update is still pending.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Check status' }));
  expect(mocks.refetch).toHaveBeenCalledOnce();
});
it('handles missing references and verification errors', () => {
  mocks.params = '';
  const view = render(<Page />);
  expect(screen.getByRole('alert')).toHaveTextContent('No subscription reference');
  view.unmount();
  mocks.params = 'plan_slug=pro'; mocks.isError = true;
  render(<Page />);
  expect(screen.getByRole('alert')).toHaveTextContent('Status unavailable');
});
