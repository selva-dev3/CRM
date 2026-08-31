import type { Metadata } from 'next';
import { Suspense } from 'react';
import { ResetPasswordForm } from '@/components/features/auth/reset-password-form';

export const metadata: Metadata = {
  title: 'Reset password | Enterprise CRM',
  description: 'Choose a new password for your Enterprise CRM account.',
};

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-600">Loading secure reset form…</p>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
