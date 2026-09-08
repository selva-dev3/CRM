'use client';

import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import {
  Building2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  useValidateInvitationQuery,
  useAcceptInvitationMutation,
  AcceptInvitationResponse
} from '@/lib/api/organizations';

export default function AcceptInvitationPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();

  // Read token from route params or ?token= query parameter
  const rawToken = (params?.token as string) || searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<AcceptInvitationResponse | null>(null);

  // Validate Invitation Token
  const { data: invStatus, isLoading: isValidating, error: validateError } = useValidateInvitationQuery(rawToken);
  const acceptMutation = useAcceptInvitationMutation();

  // Populate pre-existing invitation details
  useEffect(() => {
    if (invStatus) {
      if (invStatus.full_name) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate invite form from API status
        setFullName(invStatus.full_name);
      }
    }
  }, [invStatus]);

  useEffect(() => {
    if (!successData) return;
    const timer = setTimeout(() => router.push('/dashboard'), 3500);
    return () => clearTimeout(timer);
  }, [successData, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (acceptMutation.isPending) return;
    if (!rawToken) {
      setErrorMessage('Invitation token is missing.');
      return;
    }
    if (!password || password.length < 8) {
      setErrorMessage('Password must be at least 8 characters.');
      return;
    }
    if (new TextEncoder().encode(password).length > 72) {
      setErrorMessage('Password must be at most 72 UTF-8 bytes.');
      return;
    }
    try {
      setErrorMessage(null);
      const res = await acceptMutation.mutateAsync({
        token: rawToken,
        payload: {
          password,
          full_name: fullName.trim(),

        }
      });

      setSuccessData(res);

    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to accept invitation.'));
    }
  };

  if (isValidating) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#F9FAFB] p-4 text-center">
        <Loader2 className="w-10 h-10 animate-spin text-[#2563EB] mb-3" />
        <h2 className="text-subheading font-bold text-[#111827]">Validating Invitation Token...</h2>
        <p className="text-caption text-[#6B7280] mt-1">Checking invitation status and organization setup.</p>
      </div>
    );
  }

  if (validateError || (invStatus && !invStatus.is_valid)) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#F9FAFB] p-4">
        <Card className="max-w-md w-full p-6 bg-white border border-[#DC2626]/30 shadow-saas-md rounded-btn text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-[#DC2626]/10 text-[#DC2626] mx-auto flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-subheading font-bold text-[#111827]">Invitation Link Expired or Invalid</h2>
            <p className="text-caption text-[#6B7280] mt-1">
              This invitation token is invalid, expired, or has already been used. Please contact your organization administrator to receive a new invitation link.
            </p>
          </div>
          <Button
            onClick={() => router.push('/')}
            variant="outline"
            className="w-full cursor-pointer shadow-saas-sm border-[#E5E7EB]"
          >
            Return to Homepage
          </Button>
        </Card>
      </div>
    );
  }

  // Success Celebration View
  if (successData) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#F9FAFB] p-4">
        <Card className="max-w-lg w-full p-8 bg-white border border-[#16A34A]/30 shadow-saas-md rounded-btn text-center space-y-6 animate-in fade-in-50">
          <div className="w-16 h-16 rounded-full bg-[#16A34A]/10 text-[#16A34A] mx-auto flex items-center justify-center shadow-saas-sm">
            <CheckCircle2 className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <Badge className="bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20 font-bold px-3 py-1 text-badge">
              Account Activated!
            </Badge>
            <h2 className="text-page-title font-bold text-[#111827]">
              Welcome, {successData.user.name}!
            </h2>
            <p className="text-body text-[#6B7280]">
              {successData.message}
            </p>
          </div>

          {successData.organization && (
            <div className="p-4 bg-[#F9FAFB] border border-[#E5E7EB] rounded-btn text-left text-body space-y-2 font-mono">
              <div className="flex justify-between">
                <span className="text-[#6B7280]">Organization:</span>
                <span className="font-bold text-[#111827]">{successData.organization.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6B7280]">Org ID:</span>
                <span className="font-bold text-[#2563EB]">{successData.organization.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6B7280]">Plan Tier:</span>
                <span className="font-bold text-emerald-600">{successData.organization.plan || 'Free'} Plan</span>
              </div>
            </div>
          )}

          <div className="pt-2">
            <Button
              onClick={() => router.push('/dashboard')}
              variant="primary"
              className="w-full cursor-pointer shadow-saas-sm h-11 text-button font-bold"
            >
              <span>Go to CRM Dashboard</span>
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <p className="text-caption text-[#9CA3AF] mt-3">Redirecting to Dashboard automatically in 3 seconds...</p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-xl">
        <div className="flex items-center justify-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-btn bg-[#2563EB] text-white flex items-center justify-center font-bold shadow-saas-sm">
            <Building2 className="w-6 h-6" />
          </div>
          <span className="text-page-title font-extrabold text-[#111827] tracking-tight">Enterprise CRM</span>
        </div>

        <h2 className="text-center text-subheading font-bold text-[#111827]">
          Accept Organization Invitation
        </h2>
        <p className="mt-1 text-center text-caption text-[#6B7280]">
          Invited Email: <span className="font-mono font-bold text-[#2563EB]">{invStatus?.email || 'User'}</span>
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-xl">
        <Card className="p-8 bg-white border border-[#E5E7EB] shadow-saas-md rounded-btn space-y-6">
          <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
            <div className="flex items-center gap-2 font-semibold text-[#111827]">
              <ShieldCheck className="w-5 h-5 text-[#2563EB]" />
              <span>Your Profile</span>
            </div>

          </div>

          {errorMessage && (
            <div className="p-4 rounded-btn bg-[#DC2626]/10 border border-[#DC2626]/20 text-[#DC2626] text-body font-medium flex items-center gap-2 animate-in fade-in-50">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Account Password */}
            <div>
              <Label htmlFor="password">Set Account Password *</Label>
              <div className="relative mt-1">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Choose a password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pr-10"
                  maxLength={72}
                  required
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-[#9CA3AF] hover:text-[#374151] cursor-pointer"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-caption text-[#6B7280] mt-1">
                Use 8 to 72 characters; Unicode characters may use multiple bytes.
              </p>
            </div>

            {/* Full Name */}
            <div>
              <Label htmlFor="full_name">Full Name *</Label>
              <Input
                id="full_name"
                maxLength={255}
                placeholder="Jane Smith"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>

            <div className="pt-4 border-t border-[#E5E7EB]">
              <Button
                type="submit"
                variant="primary"
                disabled={acceptMutation.isPending}
                className="w-full cursor-pointer shadow-saas-sm h-11 text-button font-bold"
              >
                {acceptMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Activating Account...</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Accept Invitation</span>
                  </span>
                )}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
