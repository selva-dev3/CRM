import type { Metadata } from 'next';
import { LoginForm } from '@/components/features/auth/login-form';

export const metadata: Metadata = {
  title: 'Sign in | Enterprise CRM',
  description: 'Sign in to your Enterprise CRM workspace.',
};

export default function LoginPage() {
  return <LoginForm />;
}
