'use client';

import { useEffect, useRef, useState } from 'react';
import { z } from 'zod';
import { useOptionalAuth } from '@/providers/auth-provider';
import { useCreateSubscriptionCheckoutMutation, useVerifySubscriptionCheckoutQuery, isSubscriptionCheckoutComplete, redirectToSubscriptionCheckout, type CreateSubscriptionCheckoutPayload } from '@/lib/api/organizations';
import { getErrorMessage } from '@/lib/utils';
import { ApiError } from '@/lib/api/client';

const operationSchema = z.object({
  idempotencyKey: z.string().uuid(),
  payload: z.object({ plan_slug: z.string().min(1), org_id: z.string().optional() }),
});
export type SubscriptionCheckoutOperation = z.infer<typeof operationSchema>;
export const subscriptionOperationKey = (userId: string, orgId: string) => `subscription-checkout:${userId}:${orgId}`;

export function readSubscriptionOperation(key: string): SubscriptionCheckoutOperation | null {
  const raw = sessionStorage.getItem(key);
  return raw ? operationSchema.parse(JSON.parse(raw)) : null;
}

export function useSubscriptionCheckout(orgId?: string | null) {
  const auth = useOptionalAuth();
  const userId = auth?.user?.id;
  const targetOrg = orgId || auth?.user?.organization_id;
  const key = userId && targetOrg ? subscriptionOperationKey(userId, targetOrg) : null;
  const [loaded, setLoaded] = useState<string | null>(null);
  const [operation, setOperation] = useState<SubscriptionCheckoutOperation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);
  const busy = useRef(false);
  const mutation = useCreateSubscriptionCheckoutMutation();

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      try {
        setOperation(key ? readSubscriptionOperation(key) : null);
        setLoaded(key);
        setError(null);
      } catch {
        setLoaded(null);
        setError('Unable to restore the pending subscription request. Check billing status before trying again.');
      }
    });
    return () => { active = false; };
  }, [key]);

  async function start(planSlug: string) {
    if (busy.current || redirecting || !key || loaded !== key) return;
    busy.current = true;
    setError(null);
    try {
      const payload: CreateSubscriptionCheckoutPayload = { plan_slug: planSlug, ...(orgId ? { org_id: orgId } : {}) };
      const pending = readSubscriptionOperation(key);
      if (pending && pending.payload.plan_slug !== planSlug) throw new Error('Retry the pending subscription request before choosing another plan.');
      const request = pending ?? { payload, idempotencyKey: crypto.randomUUID() };
      // Persist before POST. Neither redirects nor uncertain errors prove that the operation is finished.
      sessionStorage.setItem(key, JSON.stringify(request));
      setOperation(request);
      const result = await mutation.mutateAsync(request);
      redirectToSubscriptionCheckout(result.checkout_url);
      setRedirecting(true);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409 && failure.code === 'SUBSCRIPTION_CHECKOUT_EXPIRED') {
        // This code confirms provider expiration and removal of the server's pending operation.
        try {
          sessionStorage.removeItem(key);
          setOperation(null);
          setError('The previous checkout expired. Choose a plan and try again to start a new checkout.');
        } catch {
          setError('The checkout expired, but the stored request could not be cleared. Check subscription status before trying again.');
        }
        return;
      }
      setError(getErrorMessage(failure, 'Unable to open subscription billing. Retry the same request.'));
    } finally {
      busy.current = false;
    }
  }

  return { start, operation, error, isPending: mutation.isPending || redirecting, ready: Boolean(key && loaded === key), isCurrentOrganization: !orgId || orgId === auth?.user?.organization_id };
}

export const SUBSCRIPTION_POLL_WINDOW_MS = 120_000;

export function useSubscriptionPollingWindow(identity: string) {
  const [expiredIdentity, setExpiredIdentity] = useState<string | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setExpiredIdentity(identity), SUBSCRIPTION_POLL_WINDOW_MS);
    return () => clearTimeout(timer);
  }, [identity]);
  return expiredIdentity !== identity;
}

export function useSubscriptionVerification(sessionId: string | null, planSlug: string | null) {
  const auth = useOptionalAuth();
  const polling = useSubscriptionPollingWindow(JSON.stringify([sessionId, planSlug]));
  const query = useVerifySubscriptionCheckoutQuery(sessionId, planSlug, polling);
  const complete = !query.isError && isSubscriptionCheckoutComplete(query.data, planSlug);
  const userId = auth?.user?.id;
  const orgId = auth?.user?.organization_id;
  useEffect(() => {
    if (!complete || !userId || !orgId) return;
    const key = subscriptionOperationKey(userId, orgId);
    try {
      const operation = readSubscriptionOperation(key);
      if (operation?.payload.plan_slug === query.data?.plan_slug) sessionStorage.removeItem(key);
    } catch {
      // Completion is server-confirmed; storage cleanup must not turn it into a failed payment.
    }
  }, [complete, userId, orgId, query.data?.plan_slug]);
  return { ...query, complete, polling };
}
