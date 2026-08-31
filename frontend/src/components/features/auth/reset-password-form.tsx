'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { AlertCircle, ArrowLeft, CheckCircle2, Eye, EyeOff, Loader2, Lock } from 'lucide-react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
} from '@/components/ui';
import { useResetPasswordMutation } from '@/lib/api';
import { resetPasswordSchema } from '@/lib/validators';
import { getAuthErrorMessage } from './auth-form-utils';

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';
  const mutation = useResetPasswordMutation();
  const [showPassword, setShowPassword] = useState(false);
  const [completed, setCompleted] = useState(false);
  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { newPassword: '', confirmPassword: '' },
  });

  const onSubmit = async (values: ResetPasswordFormValues) => {
    form.clearErrors('root');
    try {
      await mutation.mutateAsync({ token, new_password: values.newPassword });
      form.reset();
      setCompleted(true);
    } catch (error) {
      form.setError('root', {
        message: getAuthErrorMessage(
          error,
          'Unable to reset your password. Request a new link and try again.',
        ),
      });
    }
  };

  if (token.length < 14) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive" role="alert">
          <AlertCircle className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Invalid reset link</AlertTitle>
            <AlertDescription>This reset link is incomplete. Request a new link to continue.</AlertDescription>
          </div>
        </Alert>
        <Button asChild className="h-12 w-full px-6 text-base font-semibold">
          <Link href="/forgot-password"><span className="text-white">Request a new reset link</span></Link>
        </Button>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="space-y-6">
        <Alert variant="success" role="status">
          <CheckCircle2 className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Password updated</AlertTitle>
            <AlertDescription>You can now sign in with your new password.</AlertDescription>
          </div>
        </Alert>
        <Button asChild className="h-12 w-full px-6 text-base font-semibold">
          <Link href="/login"><span className="text-white">Continue to sign in</span></Link>
        </Button>
      </div>
    );
  }

  const formError = form.formState.errors.root?.message;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Choose a new password</h1>
        <p className="text-sm leading-6 text-slate-600">
          Use at least 8 characters. Your reset link can only be used once.
        </p>
      </header>

      {formError && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Password reset failed</AlertTitle>
            <AlertDescription>{formError}</AlertDescription>
          </div>
        </Alert>
      )}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
          {(['newPassword', 'confirmPassword'] as const).map((name) => (
            <FormField
              key={name}
              control={form.control}
              name={name}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{name === 'newPassword' ? 'New password' : 'Confirm password'}</FormLabel>
                  <div className="relative">
                    <Lock
                      className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500"
                      aria-hidden="true"
                    />
                    <FormControl>
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        autoComplete="new-password"
                        placeholder={name === 'newPassword' ? 'Enter a new password' : 'Repeat your new password'}
                        className="h-11 pl-10 pr-12"
                        disabled={mutation.isPending}
                        {...field}
                      />
                    </FormControl>
                    {name === 'newPassword' && (
                      <button
                        type="button"
                        onClick={() => setShowPassword((current) => !current)}
                        className="absolute right-0 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center text-slate-500 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-600/40"
                        aria-label={showPassword ? 'Hide passwords' : 'Show passwords'}
                        aria-pressed={showPassword}
                      >
                        {showPassword ? (
                          <EyeOff className="size-4" aria-hidden="true" />
                        ) : (
                          <Eye className="size-4" aria-hidden="true" />
                        )}
                      </button>
                    )}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}

          <Button
            type="submit"
            className="h-12 w-full px-6 text-base font-semibold"
            disabled={mutation.isPending}
          >
            <span className="inline-flex items-center gap-2 text-white">
              {mutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {mutation.isPending ? 'Updating password…' : 'Update password'}
            </span>
          </Button>
        </form>
      </Form>

      <Link
        href="/login"
        className="flex min-h-11 items-center justify-center gap-2 rounded-md text-sm font-semibold text-indigo-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600/40"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to sign in
      </Link>
    </div>
  );
}
