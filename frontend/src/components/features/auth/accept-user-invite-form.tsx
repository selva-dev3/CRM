'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { AlertCircle, Eye, EyeOff, Loader2, Lock, UserRound } from 'lucide-react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
} from '@/components/ui';
import { notifyAuthUserChanged } from '@/hooks/use-has-permission';
import { persistSessionUser } from '@/lib/auth-session';
import { useAcceptInviteMutation, useUserInvitationDetailsQuery } from '@/lib/api';
import { acceptUserInviteSchema } from '@/lib/validators';
import { getAuthErrorMessage } from './auth-form-utils';

type AcceptUserInviteFormValues = z.infer<typeof acceptUserInviteSchema>;

export function AcceptUserInviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';
  const invitationQuery = useUserInvitationDetailsQuery(token);
  const acceptMutation = useAcceptInviteMutation();
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<AcceptUserInviteFormValues>({
    resolver: zodResolver(acceptUserInviteSchema),
    defaultValues: { name: '', password: '', confirmPassword: '' },
  });

  const onSubmit = async (values: AcceptUserInviteFormValues) => {
    form.clearErrors('root');
    try {
      const result = await acceptMutation.mutateAsync({
        token,
        name: values.name,
        password: values.password,
      });
      persistSessionUser(result.user, { remember: false });
      notifyAuthUserChanged();
      router.replace('/dashboard');
    } catch (error) {
      form.setError('root', {
        message: getAuthErrorMessage(
          error,
          'Unable to accept this invitation. Request a new link and try again.',
        ),
      });
    }
  };

  if (!token) {
    return <InvitationError title="Invalid invitation link" message="This invitation link is missing its secure token." />;
  }

  if (invitationQuery.isLoading) {
    return (
      <div className="flex min-h-48 flex-col items-center justify-center gap-3" role="status">
        <Loader2 className="size-7 animate-spin text-indigo-600" aria-hidden="true" />
        <p className="text-sm font-medium text-slate-600">Validating your invitation…</p>
      </div>
    );
  }

  if (invitationQuery.isError || !invitationQuery.data) {
    return (
      <InvitationError
        title="Unable to open invitation"
        message="This invitation is invalid or no longer available. Ask your administrator for a new link."
      />
    );
  }

  if (invitationQuery.data.status !== 'pending') {
    const wasAccepted = invitationQuery.data.status === 'accepted';
    return (
      <InvitationError
        title={wasAccepted ? 'Invitation already used' : 'Invitation no longer active'}
        message={
          wasAccepted
            ? 'This invitation has already been accepted. Sign in to continue.'
            : 'This invitation has expired or was revoked. Ask your administrator for a new link.'
        }
      />
    );
  }

  const formError = form.formState.errors.root?.message;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Badge variant="secondary">{invitationQuery.data.role}</Badge>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Complete your account
        </h1>
        <p className="text-sm leading-6 text-slate-600">
          You were invited as <span className="font-semibold">{invitationQuery.data.email}</span>.
          Choose your name and password to join the workspace.
        </p>
      </header>

      {formError && (
        <Alert variant="destructive" role="alert" aria-live="polite">
          <AlertCircle className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Invitation acceptance failed</AlertTitle>
            <AlertDescription>{formError}</AlertDescription>
          </div>
        </Alert>
      )}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Full name</FormLabel>
                <div className="relative">
                  <UserRound className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                  <FormControl>
                    <Input
                      autoComplete="name"
                      placeholder="Enter your full name"
                      className="h-11 pl-10"
                      disabled={acceptMutation.isPending}
                      {...field}
                    />
                  </FormControl>
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          {(['password', 'confirmPassword'] as const).map((name) => (
            <FormField
              key={name}
              control={form.control}
              name={name}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{name === 'password' ? 'Password' : 'Confirm password'}</FormLabel>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                    <FormControl>
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        autoComplete="new-password"
                        placeholder={name === 'password' ? 'Create a password' : 'Repeat your password'}
                        className="h-11 pl-10 pr-12"
                        disabled={acceptMutation.isPending}
                        {...field}
                      />
                    </FormControl>
                    {name === 'password' && (
                      <button
                        type="button"
                        onClick={() => setShowPassword((current) => !current)}
                        className="absolute right-0 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center text-slate-500 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-600/40"
                        aria-label={showPassword ? 'Hide passwords' : 'Show passwords'}
                        aria-pressed={showPassword}
                      >
                        {showPassword ? <EyeOff className="size-4" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
                      </button>
                    )}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}

          <Button type="submit" className="h-12 w-full text-base font-semibold" disabled={acceptMutation.isPending}>
            <span className="inline-flex items-center gap-2 text-white">
              {acceptMutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {acceptMutation.isPending ? 'Creating account…' : 'Accept invitation'}
            </span>
          </Button>
        </form>
      </Form>
    </div>
  );
}

function InvitationError({ title, message }: { title: string; message: string }) {
  return (
    <div className="space-y-6">
      <Alert variant="destructive" role="alert">
        <AlertCircle className="size-5" aria-hidden="true" />
        <div>
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>{message}</AlertDescription>
        </div>
      </Alert>
      <Button asChild className="h-12 w-full text-base font-semibold">
        <Link href="/login"><span className="text-white">Continue to sign in</span></Link>
      </Button>
    </div>
  );
}
