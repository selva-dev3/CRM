import type { Metadata } from 'next';
import { Suspense } from 'react';
import { AcceptUserInviteForm } from '@/components/features/auth/accept-user-invite-form';

export const metadata: Metadata = {
  title: 'Accept invitation | Enterprise CRM',
  description: 'Complete your Enterprise CRM account invitation.',
};

export default function AcceptUserInvitePage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-600">Loading secure invitation…</p>}>
      <AcceptUserInviteForm />
    </Suspense>
  );
}
