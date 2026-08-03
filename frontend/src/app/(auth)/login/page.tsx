'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useLoginMutation } from '@/lib/api';
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

  // TanStack React Query Mutation imported from @/lib/api/auth.ts
  const loginMutation = useLoginMutation({
    onSuccess: (data) => {
      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        if (rememberMe) {
          document.cookie = `token=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
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
        <h2 className="text-3xl font-bold tracking-tight text-white">
          Sign in to your account
        </h2>
        <p className="text-sm text-slate-400">
          Enter your credentials to access your CRM workspace
        </p>
      </div>

      {/* Quick Demo Pre-fill Banner */}
      <div className="p-3.5 rounded-xl bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 border border-indigo-500/20 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <p className="text-xs font-semibold text-white">Testing backend API?</p>
            <p className="text-[11px] text-slate-400">Click to fill Superadmin credentials</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleQuickDemoFill}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition shadow-md shadow-indigo-600/20 active:scale-95 cursor-pointer"
        >
          Quick Fill
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-start space-x-3 animate-in fade-in slide-in-from-top-2 duration-200">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold block mb-0.5">Authentication Error</span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Success Alert */}
      {success && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm flex items-center space-x-3 animate-in fade-in slide-in-from-top-2 duration-200">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Email Field */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Work Email
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <Mail className="w-4 h-4" />
            </div>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className="w-full pl-10 pr-4 py-3 bg-slate-900/90 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition duration-200 text-sm"
            />
          </div>
        </div>

        {/* Password Field */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Password
            </label>
            <Link
              href="/forgot-password"
              className="text-xs font-medium text-indigo-400 hover:text-indigo-300 transition"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <Lock className="w-4 h-4" />
            </div>
            <input
              type={showPassword ? 'text' : 'password'}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full pl-10 pr-10 py-3 bg-slate-900/90 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition duration-200 text-sm"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300 transition cursor-pointer"
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
              className="w-4 h-4 rounded border-slate-800 bg-slate-900 text-indigo-600 focus:ring-indigo-500/20 focus:ring-offset-slate-950 accent-indigo-600"
            />
            <span className="text-xs text-slate-400 font-medium">Keep me signed in</span>
          </label>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loginMutation.isPending}
          className="w-full py-3.5 px-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 hover:from-indigo-500 hover:via-purple-500 hover:to-indigo-500 text-white font-semibold text-sm rounded-xl shadow-lg shadow-indigo-600/25 transition duration-200 flex items-center justify-center space-x-2 disabled:opacity-60 cursor-pointer active:scale-[0.99]"
        >
          {loginMutation.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-white" />
              <span>Authenticating with TanStack Query...</span>
            </>
          ) : (
            <>
              <span>Sign In to CRM</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      {/* Backend API Indicator */}
      <div className="pt-2 text-center">
        <span className="inline-flex items-center space-x-1.5 text-[11px] text-slate-500">
          <Globe className="w-3 h-3 text-emerald-400 animate-pulse" />
          <span>TanStack Module <code className="text-indigo-400 font-mono">@/lib/api/auth.ts</code> + Railway API</span>
        </span>
      </div>

      {/* Register Redirect Footer */}
      <div className="text-center text-xs text-slate-400 pt-4 border-t border-slate-800/80">
        Don&apos;t have an account yet?{' '}
        <Link
          href="/register"
          className="font-semibold text-indigo-400 hover:text-indigo-300 underline underline-offset-4 transition"
        >
          Create Organization Account
        </Link>
      </div>
    </div>
  );
}
