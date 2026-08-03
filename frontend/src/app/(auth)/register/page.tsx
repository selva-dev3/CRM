'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useRegisterMutation } from '@/lib/api';
import { Button, Input, Label, Alert, AlertTitle, AlertDescription } from '@/components/ui';
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
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Create your account
        </h2>
        <p className="text-xs text-slate-500">
          Start your 14-day free trial. No credit card required.
        </p>
      </div>

      {/* Shadcn Error Alert */}
      {error && (
        <Alert variant="destructive" className="animate-in fade-in slide-in-from-top-2 duration-200">
          <AlertCircle className="w-5 h-5 text-rose-600" />
          <div>
            <AlertTitle>Registration Error</AlertTitle>
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
        {/* Full Name */}
        <div>
          <Label htmlFor="fullName">Full Name</Label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <Input
              id="fullName"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Selvakumar Dev"
              className="pl-10"
            />
          </div>
        </div>

        {/* Work Email */}
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

        {/* Organization / Company Name */}
        <div>
          <Label htmlFor="orgName">Organization Name</Label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Building2 className="w-4 h-4" />
            </div>
            <Input
              id="orgName"
              type="text"
              required
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              placeholder="Acme Enterprise Corp"
              className="pl-10"
            />
          </div>
        </div>

        {/* Password Field */}
        <div>
          <Label htmlFor="password">Password</Label>
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
              placeholder="Create a password"
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

          {/* Password Strength Indicator */}
          {password.length > 0 && (
            <div className="mt-2.5 space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">Password Strength:</span>
                <span className={`font-semibold ${
                  pwdStrength <= 1 ? 'text-rose-600' : pwdStrength <= 3 ? 'text-amber-600' : 'text-emerald-600'
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
                        : 'bg-slate-200'
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
              className="w-4 h-4 mt-0.5 rounded border-slate-300 bg-white text-indigo-600 focus:ring-indigo-500/20 accent-indigo-600 shrink-0"
            />
            <span className="text-xs text-slate-500 leading-normal">
              I agree to the{' '}
              <a href="#" className="text-indigo-600 font-semibold hover:underline">Terms of Service</a>
              {' '}and{' '}
              <a href="#" className="text-indigo-600 font-semibold hover:underline">Privacy Policy</a>
            </span>
          </label>
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          disabled={registerMutation.isPending}
          className="w-full py-3.5"
        >
          {registerMutation.isPending ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              <span>Creating Account...</span>
            </>
          ) : (
            <>
              <span>Create Account</span>
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

      {/* Login Redirect Footer */}
      <div className="text-center text-xs text-slate-500 pt-4 border-t border-slate-100">
        Already have an account?{' '}
        <Link
          href="/login"
          className="font-bold text-indigo-600 hover:text-indigo-700 underline underline-offset-4 transition"
        >
          Sign In instead
        </Link>
      </div>
    </div>
  );
}
