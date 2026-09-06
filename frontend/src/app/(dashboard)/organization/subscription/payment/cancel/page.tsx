import Link from 'next/link';

export default function SubscriptionPaymentPage() {
  return <main className="mx-auto max-w-xl space-y-4 p-6"><h1 className="text-xl font-semibold">Subscription checkout cancelled</h1><p>You returned without completing the Stripe flow. This page does not verify payment or subscription status.</p><p>Return to billing to review your subscription or resume the pending request.</p><Link href="/organization/subscription/plans" className="underline">View subscription plans</Link></main>;
}
