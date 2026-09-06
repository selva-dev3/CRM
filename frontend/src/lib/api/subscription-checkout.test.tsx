import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { apiClient, ApiError } from './client';
import { createSubscriptionCheckoutApi, validateSubscriptionRedirect, verifySubscriptionCheckoutApi, isSubscriptionCheckoutComplete, useVerifySubscriptionCheckoutQuery, redirectToSubscriptionCheckout, useResumeSubscriptionMutation } from './organizations';
import { SUBSCRIPTION_POLL_WINDOW_MS, subscriptionOperationKey, useSubscriptionCheckout, useSubscriptionVerification } from './subscription-checkout';

vi.mock('./client', async (importOriginal) => ({ ...await importOriginal<typeof import('./client')>(), apiClient: { post: vi.fn(), get: vi.fn() } }));
vi.mock('@/providers/auth-provider', () => ({ useOptionalAuth: () => ({ user: { id: 'user-1', organization_id: 'org-1' } }) }));
vi.mock('./organizations', async (importOriginal) => ({ ...await importOriginal<typeof import('./organizations')>(), redirectToSubscriptionCheckout: vi.fn() }));

const completed = { verified: true, db_synced: true, status: 'completed' as const, plan: 'Pro', plan_slug: 'pro', message: 'Updated' };
const pending = { ...completed, verified: false, db_synced: false, status: 'pending' as const };
const clients: QueryClient[] = [];
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  return { client, wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> };
}
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear();
  vi.mocked(apiClient.post).mockResolvedValue({ checkout_url: 'https://checkout.stripe.com/c/pay/cs_test', session_id: 'cs_test', status: 'success' });
  vi.mocked(apiClient.get).mockResolvedValue(pending);
});
afterEach(() => { clients.forEach(client => client.clear()); clients.length = 0; vi.useRealTimers(); });

describe('subscription contract', () => {
  it.each(['https://checkout.stripe.com/c/pay/test', 'https://billing.stripe.com/p/session/test'])('permits %s', (url) => {
    expect(validateSubscriptionRedirect(url)).toBe(url);
  });
  it.each(['http://checkout.stripe.com/a', 'https://checkout.stripe.com.evil.test/a', 'https://evil.test/', 'javascript:alert(1)', 'https://user@billing.stripe.com/a', 'https://billing.stripe.com:444/a', '//checkout.stripe.com/a'])('rejects %s', (url) => {
    expect(() => validateSubscriptionRedirect(url)).toThrow();
  });
  it('sends exact payload and UUID header and accepts a portal response with null session', async () => {
    const key = crypto.randomUUID();
    vi.mocked(apiClient.post).mockResolvedValue({ checkout_url: 'https://billing.stripe.com/p/session/a', session_id: null, status: 'success' });
    expect((await createSubscriptionCheckoutApi({ plan_slug: 'pro', org_id: 'org-1' }, key)).session_id).toBeNull();
    expect(apiClient.post).toHaveBeenCalledWith('/organizations/subscription/checkout', { plan_slug: 'pro', org_id: 'org-1' }, { headers: { 'Idempotency-Key': key } });
  });
  it('rejects a non-Stripe URL from the API', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ checkout_url: 'https://evil.test/', session_id: null, status: 'success' });
    await expect(createSubscriptionCheckoutApi({ plan_slug: 'pro' }, crypto.randomUUID())).rejects.toThrow();
  });
  it('uses read-only verification with either or both optional query parameters', async () => {
    await verifySubscriptionCheckoutApi(null, 'pro');
    expect(apiClient.get).toHaveBeenLastCalledWith('/organizations/subscription/checkout/verify?plan_slug=pro');
    await verifySubscriptionCheckoutApi('cs_1', 'pro');
    expect(apiClient.get).toHaveBeenLastCalledWith('/organizations/subscription/checkout/verify?session_id=cs_1&plan_slug=pro');
    expect(apiClient.post).not.toHaveBeenCalled();
  });
  it('requires all completion signals', () => {
    expect(isSubscriptionCheckoutComplete(completed)).toBe(true);
    expect(isSubscriptionCheckoutComplete(completed, 'enterprise')).toBe(false);
    for (const override of [{ verified: false }, { db_synced: false }, { status: 'pending' as const }]) expect(isSubscriptionCheckoutComplete({ ...completed, ...override })).toBe(false);
  });
});

describe('subscription hooks', () => {
  it('resumes renewal through the existing API and invalidates subscription state', async () => {
    const { client, wrapper } = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    vi.mocked(apiClient.post).mockResolvedValue({ status: 'success', message: 'Renewal enabled' });
    const { result } = renderHook(() => useResumeSubscriptionMutation(), { wrapper });
    await act(async () => { await result.current.mutateAsync(); });
    expect(apiClient.post).toHaveBeenCalledWith('/organizations/subscription/resume');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['organization-subscription'] });
  });

  it('keeps the same operation after configuration errors and requires administrator review', async () => {
    const { wrapper } = setup();
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError('Ask an administrator to review billing.', 'http', 502, 'SUBSCRIPTION_PROVIDER_ERROR', { retryable: false }));
    const { result } = renderHook(() => useSubscriptionCheckout(), { wrapper });
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(async () => { await result.current.start('pro'); });
    expect(result.current.requiresAdministratorReview).toBe(true);
    const operation = result.current.operation;
    expect(operation).not.toBeNull();
    expect(result.current.error).toBe('Ask an administrator to review billing.');
    await act(async () => { await result.current.start('pro'); });
    expect(result.current.operation).toEqual(operation);
    expect(JSON.parse(sessionStorage.getItem(subscriptionOperationKey('user-1', 'org-1')) ?? 'null')).toEqual(operation);
  });
  it('clears a server-confirmed expired operation and uses a fresh UUID for another plan', async () => {
    const key = subscriptionOperationKey('user-1', 'org-1');
    const originalKey = crypto.randomUUID();
    sessionStorage.setItem(key, JSON.stringify({ payload: { plan_slug: 'pro' }, idempotencyKey: originalKey }));
    vi.mocked(apiClient.post).mockRejectedValueOnce(new ApiError('Expired', 'http', 409, 'SUBSCRIPTION_CHECKOUT_EXPIRED'));
    const { result } = renderHook(() => useSubscriptionCheckout(), { wrapper: setup().wrapper });
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(() => result.current.start('pro'));
    expect(sessionStorage.getItem(key)).toBeNull();
    expect(result.current.operation).toBeNull();
    expect(result.current.error).toMatch(/Choose a plan and try again/);
    await act(() => result.current.start('enterprise'));
    const request = vi.mocked(apiClient.post).mock.calls[1];
    expect(request[1]).toEqual({ plan_slug: 'enterprise' });
    const headers = new Headers(request[2]?.headers);
    expect(headers.get('Idempotency-Key')).not.toBe(originalKey);
    expect(headers.get('Idempotency-Key')).toMatch(/^[0-9a-f-]{36}$/);
  });
  it.each([
    [409, 'SUBSCRIPTION_CHECKOUT_COMPLETED'],
    [409, 'SUBSCRIPTION_CHECKOUT_IN_PROGRESS'],
    [409, 'CONFLICT'],
    [409, 'UNKNOWN'],
    [400, 'UNKNOWN_PLAN'],
    [400, 'SUBSCRIPTION_CHECKOUT_EXPIRED'],
    [502, 'SUBSCRIPTION_CHECKOUT_EXPIRED'],
  ])('retains the operation for %s %s', async (status, code) => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(new ApiError('Request failed', 'http', status, code));
    const { result } = renderHook(() => useSubscriptionCheckout(), { wrapper: setup().wrapper });
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(() => result.current.start('pro'));
    expect(result.current.operation?.payload.plan_slug).toBe('pro');
    expect(sessionStorage.getItem(subscriptionOperationKey('user-1', 'org-1'))).not.toBeNull();
  });
  it('retains the same UUID and payload after an uncertain error and remount', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(new Error('Timed out'));
    const first = renderHook(() => useSubscriptionCheckout(), { wrapper: setup().wrapper });
    await waitFor(() => expect(first.result.current.ready).toBe(true));
    await act(() => first.result.current.start('pro'));
    const original = vi.mocked(apiClient.post).mock.calls[0];
    expect(first.result.current.error).toBe('Timed out');
    first.unmount();
    const next = renderHook(() => useSubscriptionCheckout(), { wrapper: setup().wrapper });
    await waitFor(() => expect(next.result.current.operation?.payload.plan_slug).toBe('pro'));
    await act(() => next.result.current.start('pro'));
    expect(vi.mocked(apiClient.post).mock.calls[1]).toEqual(original);
    expect(redirectToSubscriptionCheckout).toHaveBeenCalledWith('https://checkout.stripe.com/c/pay/cs_test');
    expect(sessionStorage.getItem(subscriptionOperationKey('user-1', 'org-1'))).not.toBeNull();
  });
  it('blocks duplicate starts and a different plan while the outcome is uncertain', async () => {
    let rejectRequest: (reason: Error) => void = () => {};
    vi.mocked(apiClient.post).mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    const { result } = renderHook(() => useSubscriptionCheckout(), { wrapper: setup().wrapper });
    await waitFor(() => expect(result.current.ready).toBe(true));
    let request: Promise<void>;
    act(() => { request = result.current.start('pro'); void result.current.start('pro'); });
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    await act(async () => { rejectRequest(new Error('Network failure')); await request; });
    await act(() => result.current.start('enterprise'));
    expect(apiClient.post).toHaveBeenCalledTimes(1);
    expect(result.current.error).toMatch(/Retry the pending/);
  });
  it('does not request verification with no reference', () => {
    renderHook(() => useVerifySubscriptionCheckoutQuery(null, null), { wrapper: setup().wrapper });
    expect(apiClient.get).not.toHaveBeenCalled();
  });
  it('refreshes subscription caches only after verified synchronization', async () => {
    const { wrapper, client } = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const { result } = renderHook(() => useVerifySubscriptionCheckoutQuery(null, 'pro'), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidate).not.toHaveBeenCalled();
    vi.mocked(apiClient.get).mockResolvedValue(completed);
    await act(() => result.current.refetch());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['organization-subscription'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['organization-usage'] });
  });
  it('bounds polling even with no session and no verified webhook', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    const { result } = renderHook(() => useSubscriptionVerification(null, 'pro'), { wrapper: setup().wrapper });
    await act(async () => { await vi.advanceTimersByTimeAsync(SUBSCRIPTION_POLL_WINDOW_MS + 50); });
    expect(result.current.polling).toBe(false);
    expect(result.current.complete).toBe(false);
    const count = vi.mocked(apiClient.get).mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(apiClient.get).toHaveBeenCalledTimes(count);
  });
  it('clears the pending request only after authoritative completion', async () => {
    const key = subscriptionOperationKey('user-1', 'org-1');
    sessionStorage.setItem(key, JSON.stringify({ payload: { plan_slug: 'pro' }, idempotencyKey: crypto.randomUUID() }));
    vi.mocked(apiClient.get).mockResolvedValue(completed);
    const { result } = renderHook(() => useSubscriptionVerification(null, 'pro'), { wrapper: setup().wrapper });
    await waitFor(() => expect(result.current.complete).toBe(true));
    await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  });
});
