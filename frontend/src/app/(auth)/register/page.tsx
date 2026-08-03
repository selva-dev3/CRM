'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useRegisterMutation } from '@/lib/api';
import {
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Lock,
  Mail,
  User,
  Building2,
  Loader2,
  Globe
} from 'lucide-react';

export default function RegisterPage() {
  const router = useRouter();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [organizationName, setOrganizationName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // TanStack React Query Mutation imported from @/lib/api/auth.ts
  const registerMutation = useRegisterMutation({
    onSuccess: () => {
      setSuccess('Organization Account created successfully! Redirecting to login...');
      setTimeout(() => {
        router.push('/login');
      }, 1200);
    },
    onError: (err: any) => {
      setError(err.message || 'Registration failed. An account with this email may already exist.');
    },
  });

  // Password strength logic
  const getPasswordStrength = (pass: string) => {
    let score = 0;
    if (pass.length >= 8) score++;
    if (/[A-Z]/.test(pass)) score++;
    if (/[0-9]/.test(pass)) score++;
    if (/[^A-Za-z0-9]/.test(pass)) score++;
    return score; // 0 to 4
  };

  const pwdStrength = getPasswordStrength(password);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password || !organizationName) {
      setError('Please fill in all required fields.');
      return;
    }

    if (!agreeTerms) {
      setError('You must accept the Terms of Service to create an account.');
      return;
    }

    setError(null);
    setSuccess(null);

    registerMutation.mutate({
      name: name.trim(),
      email: email.trim(),
      password: password,
      organization_name: organizationName.trim(),
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2 text-center lg:text-left">
        <h2 className="text-3xl font-bold tracking-tight text-white">
          Create your account
        </h2>
        <p className="text-sm text-slate-400">
          Start your 14-day free trial. No credit card required.
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-start space-x-3 animate-in fade-in slide-in-from-top-2 duration-200">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold block mb-0.5">Registration Error</span>
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
        {/* Full Name */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Full Name
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <User className="w-4 h-4" />
            </div>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Selvakumar Dev"
              className="w-full pl-10 pr-4 py-3 bg-slate-900/90 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition duration-200 text-sm"
            />
          </div>
        </div>

        {/* Work Email */}
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

        {/* Organization / Company Name */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Organization Name
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <Building2 className="w-4 h-4" />
            </div>
            <input
              type="text"
              required
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              placeholder="Acme Enterprise Corp"
              className="w-full pl-10 pr-4 py-3 bg-slate-900/90 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition duration-200 text-sm"
            />
          </div>
        </div>

        {/* Password Field */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
            Password
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <Lock className="w-4 h-4" />
            </div>
            <input
              type={showPassword ? 'text' : 'password'}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create a password"
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

          {/* Password Strength Indicator */}
          {password.length > 0 && (
            <div className="mt-2.5 space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-400">Password Strength:</span>
                <span className={`font-semibold ${
                  pwdStrength <= 1 ? 'text-rose-400' : pwdStrength <= 3 ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {pwdStrength <= 1 ? 'Weak' : pwdStrength <= 3 ? 'Medium' : 'Strong'}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                {[1, 2, 3, 4].map((step) => (
                  <div
                    key={step}
                    className={`h-1.5 rounded-full transition-colors duration-300 ${
                      step <= pwdStrength
                        ? pwdStrength <= 1
                          ? 'bg-rose-500'
                          : pwdStrength <= 3
                          ? 'bg-amber-500'
                          : 'bg-emerald-500'
                        : 'bg-slate-800'
                    }`}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Agree Terms Checkbox */}
        <div className="pt-1">
          <label className="flex items-start space-x-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={agreeTerms}
              onChange={(e) => setAgreeTerms(e.target.checked)}
              className="w-4 h-4 mt-0.5 rounded border-slate-800 bg-slate-900 text-indigo-600 focus:ring-indigo-500/20 focus:ring-offset-slate-950 accent-indigo-600 shrink-0"
            />
            <span className="text-xs text-slate-400 leading-normal">
              I agree to the{' '}
              <a href="#" className="text-indigo-400 hover:underline">Terms of Service</a>
              {' '}and{' '}
              <a href="#" className="text-indigo-400 hover:underline">Privacy Policy</a>
            </span>
          </label>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={registerMutation.isPending}
          className="w-full py-3.5 px-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 hover:from-indigo-500 hover:via-purple-500 hover:to-indigo-500 text-white font-semibold text-sm rounded-xl shadow-lg shadow-indigo-600/25 transition duration-200 flex items-center justify-center space-x-2 disabled:opacity-60 cursor-pointer active:scale-[0.99]"
        >
          {registerMutation.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-white" />
              <span>Creating Account with TanStack Query...</span>
            </>
          ) : (
            <>
              <span>Create Account</span>
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

      {/* Login Redirect Footer */}
      <div className="text-center text-xs text-slate-400 pt-4 border-t border-slate-800/80">
        Already have an account?{' '}
        <Link
          href="/login"
          className="font-semibold text-indigo-400 hover:text-indigo-300 underline underline-offset-4 transition"
        >
          Sign In instead
        </Link>
      </div>
    </div>
  );
}
