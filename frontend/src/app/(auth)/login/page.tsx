'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useLoginMutation } from '@/lib/api';
import { getSessionToken, setSessionToken } from '@/lib/api/client';
import { notifyAuthUserChanged } from '@/hooks/use-has-permission';
import { Button, Input, Label, Alert, AlertTitle, AlertDescription } from '@/components/ui';
import { 
  ArrowRight, 
  CheckCircle2, 
  AlertCircle, 
  Eye, 
  EyeOff, 
  Lock, 
  Mail, 
  Loader2, 
  Zap,
  Globe
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // If user already has a valid token in session/storage, auto-redirect to dashboard
  useEffect(() => {
    const existingToken = getSessionToken();
    if (existingToken) {
      router.push('/dashboard');
    }
  }, [router]);

  // TanStack React Query Mutation imported from @/lib/api/auth.ts
  const loginMutation = useLoginMutation({
    onSuccess: (data) => {
      if (data.access_token) {
        setSessionToken(data.access_token, rememberMe);

        if (data.user) {
          localStorage.setItem('user', JSON.stringify(data.user));
          sessionStorage.setItem('user', JSON.stringify(data.user));
          notifyAuthUserChanged();
        }

        setSuccess('Authentication successful! Redirecting to dashboard...');
        
        setTimeout(() => {
          router.push('/dashboard');
        }, 800);
      }
    },
    onError: (err: any) => {
      setError(err.message || 'Login failed. Please verify your credentials and try again.');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    setError(null);
    setSuccess(null);

    loginMutation.mutate({
      email: email.trim(),
      password: password,
    });
  };

  const handleQuickDemoFill = () => {
    setEmail('superadmin@gmail.com');
    setPassword('password123');
    setError(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2 text-center lg:text-left">
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Sign in to your account
        </h2>
        <p className="text-xs text-slate-500">
          Enter your credentials to access your CRM workspace
        </p>
      </div>

      {/* Quick Demo Pre-fill Banner */}
      <div className="p-3.5 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-600 text-white shadow-xs">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-900">Testing backend API?</p>
            <p className="text-[11px] text-slate-500">Click to fill Superadmin credentials</p>
          </div>
        </div>
        <Button
          type="button"
          size="sm"
          variant="default"
          onClick={handleQuickDemoFill}
        >
          Quick Fill
        </Button>
      </div>

      {/* Shadcn Error Alert */}
      {error && (
        <Alert variant="destructive" className="animate-in fade-in slide-in-from-top-2 duration-200">
          <AlertCircle className="w-5 h-5 text-rose-600" />
          <div>
            <AlertTitle>Authentication Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </div>
        </Alert>
      )}

      {/* Shadcn Success Alert */}
      {success && (
        <Alert variant="success" className="animate-in fade-in slide-in-from-top-2 duration-200">
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          <div>
            <AlertTitle>Success</AlertTitle>
            <AlertDescription>{success}</AlertDescription>
          </div>
        </Alert>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Email Field */}
        <div>
          <Label htmlFor="email">Work Email</Label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Mail className="w-4 h-4" />
            </div>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className="pl-10"
            />
          </div>
        </div>

        {/* Password Field */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <Label htmlFor="password">Password</Label>
            <Link
              href="/forgot-password"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 transition"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"
              className="pl-10 pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition cursor-pointer"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Remember Me Checkbox */}
        <div className="flex items-center justify-between pt-1">
          <label className="flex items-center space-x-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 bg-white text-indigo-600 focus:ring-indigo-500/20 accent-indigo-600"
            />
            <span className="text-xs text-slate-600 font-medium">Keep me signed in</span>
          </label>
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          disabled={loginMutation.isPending}
          className="w-full py-3.5"
        >
          {loginMutation.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              <span>Authenticating...</span>
            </>
          ) : (
            <>
              <span>Sign In to CRM</span>
              <ArrowRight className="w-4 h-4 ml-2" />
            </>
          )}
        </Button>
      </form>

      {/* Backend API Indicator */}
      <div className="pt-2 text-center">
        <span className="inline-flex items-center space-x-1.5 text-[11px] text-slate-500">
          <Globe className="w-3 h-3 text-emerald-600 animate-pulse" />
          <span>Connected to Railway Production API: <code className="text-slate-700 font-mono">crm-dev3.up.railway.app</code></span>
        </span>
      </div>

      {/* Register Redirect Footer */}
      <div className="text-center text-xs text-slate-500 pt-4 border-t border-slate-100">
        Don&apos;t have an account yet?{' '}
        <Link
          href="/register"
          className="font-bold text-indigo-600 hover:text-indigo-700 underline underline-offset-4 transition"
        >
          Create Organization Account
        </Link>
      </div>
    </div>
  );
}
