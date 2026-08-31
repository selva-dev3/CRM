'use client';

import { useState } from 'react';
import Link from 'next/link';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2, Mail } from 'lucide-react';
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
import { useForgotPasswordMutation } from '@/lib/api';
import { forgotPasswordSchema } from '@/lib/validators';
import { getAuthErrorMessage } from './auth-form-utils';

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export function ForgotPasswordForm() {
  const mutation = useForgotPasswordMutation();
  const [submitted, setSubmitted] = useState(false);
  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  });

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    form.clearErrors('root');
    try {
      await mutation.mutateAsync(values);
      setSubmitted(true);
    } catch (error) {
      form.setError('root', {
        message: getAuthErrorMessage(error, 'Unable to request a reset link. Please try again.'),
      });
    }
  };

  if (submitted) {
    return (
      <div className="space-y-6">
        <Alert variant="success" role="status">
          <CheckCircle2 className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Check your email</AlertTitle>
            <AlertDescription>
              If an account exists for that address, we sent a password reset link.
            </AlertDescription>
          </div>
        </Alert>
        <Button asChild variant="outline" className="h-12 w-full px-6 text-base font-semibold">
          <Link href="/login">
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back to sign in
          </Link>
        </Button>
      </div>
    );
  }

  const formError = form.formState.errors.root?.message;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Reset your password</h1>
        <p className="text-sm leading-6 text-slate-600">
          Enter your work email and we’ll send you a secure reset link.
        </p>
      </header>

      {formError && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Request failed</AlertTitle>
            <AlertDescription>{formError}</AlertDescription>
          </div>
        </Alert>
      )}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Work email</FormLabel>
                <div className="relative">
                  <Mail
                    className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500"
                    aria-hidden="true"
                  />
                  <FormControl>
                    <Input
                      type="email"
                      inputMode="email"
                      autoComplete="email"
                      placeholder="name@company.com"
                      className="h-11 pl-10"
                      disabled={mutation.isPending}
                      {...field}
                    />
                  </FormControl>
                </div>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button
            type="submit"
            className="h-12 w-full px-6 text-base font-semibold"
            disabled={mutation.isPending}
          >
            <span className="inline-flex items-center gap-2 text-white">
              {mutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {mutation.isPending ? 'Sending reset link…' : 'Send reset link'}
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
