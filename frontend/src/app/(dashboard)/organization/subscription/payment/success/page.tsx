'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useSubscriptionVerification } from '@/lib/api/subscription-checkout';
import { getErrorMessage } from '@/lib/utils';

function PaymentSuccessContent() {
  const params = useSearchParams();
  const sessionId = params.get('session_id')?.trim() || null;
  const planSlug = params.get('plan_slug')?.trim() || null;
  const verification = useSubscriptionVerification(sessionId, planSlug);
  const hasReference = Boolean(sessionId || planSlug);

  return <main className="mx-auto max-w-xl p-4 sm:p-8"><Card className="space-y-5 p-6">
    <h1 className="text-xl font-semibold">{verification.complete ? 'Subscription updated' : 'Subscription verification'}</h1>
    {!hasReference ? <p role="alert">No subscription reference was provided. Return to billing to review your subscription.</p>
      : verification.complete ? <div role="status"><p>Your subscription update is verified and synchronized.</p><p>Plan: {verification.data?.plan || verification.data?.plan_slug}</p></div>
      : verification.isError ? <p role="alert">{getErrorMessage(verification.error, 'Unable to verify subscription status.')}</p>
      : verification.isLoading ? <p role="status">Verifying subscription status…</p>
      : <div role="status"><p>{verification.polling ? 'Waiting for billing synchronization…' : 'Subscription update is still pending.'}</p><p>{verification.data?.message || 'Your subscription has not yet been confirmed.'}</p>{!verification.polling && <p>Automatic checks have stopped. Check status again or contact your administrator.</p>}</div>}
    {hasReference && !verification.complete && (!verification.polling || verification.isError) && <Button disabled={verification.isFetching} onClick={() => void verification.refetch()}>{verification.isFetching ? 'Checking…' : 'Check status'}</Button>}
    <Button asChild variant="outline"><Link href="/organization">Return to Subscription & Billing</Link></Button>
  </Card></main>;
}

export default function SubscriptionPaymentPage() {
  return <Suspense fallback={<p role="status">Verifying subscription status…</p>}><PaymentSuccessContent /></Suspense>;
}
