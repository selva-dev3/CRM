import type { Metadata } from 'next';
import { ForgotPasswordForm } from '@/components/features/auth/forgot-password-form';

export const metadata: Metadata = {
  title: 'Forgot password | Enterprise CRM',
  description: 'Request a secure password reset link for your Enterprise CRM account.',
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
