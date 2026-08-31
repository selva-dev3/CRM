'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail } from 'lucide-react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Checkbox,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
} from '@/components/ui';
import { notifyAuthUserChanged } from '@/hooks/use-has-permission';
import { useLoginMutation } from '@/lib/api';
import { getSessionToken, setSessionToken } from '@/lib/api/client';
import { loginSchema } from '@/lib/validators';
import { getAuthErrorMessage } from './auth-form-utils';

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const router = useRouter();
  const loginMutation = useLoginMutation();
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
      rememberMe: false,
    },
  });

  useEffect(() => {
    if (getSessionToken()) {
      router.replace('/dashboard');
    }
  }, [router]);

  const onSubmit = async (values: LoginFormValues) => {
    form.clearErrors('root');

    try {
      const data = await loginMutation.mutateAsync({
        email: values.email,
        password: values.password,
      });
      if (!data.access_token) {
        throw new Error('The server did not return a valid session. Please try again.');
      }

      setSessionToken(data.access_token, values.rememberMe);
      if (data.user) {
        const serializedUser = JSON.stringify(data.user);
        sessionStorage.setItem('user', serializedUser);
        if (values.rememberMe) {
          localStorage.setItem('user', serializedUser);
        } else {
          localStorage.removeItem('user');
        }
        notifyAuthUserChanged();
      }

      router.replace('/dashboard');
    } catch (error) {
      form.setError('root', {
        message: getAuthErrorMessage(
          error,
          'Unable to sign in. Check your credentials and try again.',
        ),
      });
    }
  };

  const formError = form.formState.errors.root?.message;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Sign in to your account
        </h1>
        <p className="text-sm leading-6 text-slate-600">
          Enter your credentials to access your CRM workspace.
        </p>
      </header>

      {formError && (
        <Alert variant="destructive" role="alert" aria-live="polite">
          <AlertCircle className="size-5" aria-hidden="true" />
          <div>
            <AlertTitle>Unable to sign in</AlertTitle>
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
                      disabled={loginMutation.isPending}
                      {...field}
                    />
                  </FormControl>
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between gap-4">
                  <FormLabel>Password</FormLabel>
                  <Link
                    href="/forgot-password"
                    className="rounded-sm text-sm font-semibold text-indigo-700 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600/40"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Lock
                    className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500"
                    aria-hidden="true"
                  />
                  <FormControl>
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      placeholder="Enter your password"
                      className="h-11 pl-10 pr-12"
                      disabled={loginMutation.isPending}
                      {...field}
                    />
                  </FormControl>
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute right-0 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center text-slate-500 transition hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-600/40"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" aria-hidden="true" />
                    ) : (
                      <Eye className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="rememberMe"
            render={({ field }) => (
              <FormItem className="flex min-h-11 grid-cols-none flex-row items-center gap-3 space-y-0">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={(checked) => field.onChange(checked === true)}
                    disabled={loginMutation.isPending}
                  />
                </FormControl>
                <FormLabel className="cursor-pointer font-medium text-slate-700">
                  Keep me signed in on this device
                </FormLabel>
              </FormItem>
            )}
          />

          <Button
            type="submit"
            className="h-12 w-full px-6 text-base font-semibold"
            disabled={loginMutation.isPending}
          >
            <span className="inline-flex items-center gap-2 text-white">
              {loginMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in to CRM
                  <ArrowRight className="size-4" aria-hidden="true" />
                </>
              )}
            </span>
          </Button>
        </form>
      </Form>

      <p className="border-t border-slate-200 pt-5 text-center text-sm text-slate-600">
        New to Enterprise CRM?{' '}
        <Link
          href="/register"
          className="font-semibold text-indigo-700 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600/40"
        >
          Create your organization
        </Link>
      </p>
    </div>
  );
}
