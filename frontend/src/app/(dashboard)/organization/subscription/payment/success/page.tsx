'use client';

import React, { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Zap,
  Building2,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  useOrganizationSubscriptionQuery,
  useCurrentOrganizationQuery,
  useVerifySubscriptionCheckoutQuery,
} from '@/lib/api/organizations';

function PaymentSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const sessionId = searchParams.get('session_id');
  const orgId = searchParams.get('org_id');

  const {
    data: verifyResult,
    isLoading: isVerifying,
    isError: isVerifyError,
    refetch: refetchVerify,
  } = useVerifySubscriptionCheckoutQuery(sessionId, orgId);

  const { data: subscription, refetch: refetchSubscription } =
    useOrganizationSubscriptionQuery();
  const { data: org } = useCurrentOrganizationQuery();

  useEffect(() => {
    if (verifyResult?.verified && verifyResult?.db_synced) {
      queryClient.invalidateQueries({ queryKey: ['organization-subscription'] });
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
      queryClient.invalidateQueries({ queryKey: ['organization-usage'] });
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      refetchSubscription();
    }
  }, [verifyResult, queryClient, refetchSubscription]);

  const handleReturn = () => {
    if (orgId) {
      router.push(`/organization/${encodeURIComponent(orgId)}`);
    } else if (org?.id) {
      router.push(`/organization/${encodeURIComponent(org.id)}`);
    } else {
      router.push('/organization');
    }
  };

  // State 1: No session ID provided in URL
  if (!sessionId) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
        <div className="max-w-md w-full space-y-6">
          <Card className="p-8 bg-white border border-[#E5E7EB] rounded-2xl shadow-saas-md text-center space-y-6">
            <div className="mx-auto w-16 h-16 bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-full flex items-center justify-center text-[#EF4444]">
              <ShieldAlert className="w-9 h-9" />
            </div>
            <div className="space-y-2">
              <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                Missing Checkout Session
              </Badge>
              <h1 className="text-2xl font-bold text-[#111827] tracking-tight">
                No Payment Session Found
              </h1>
              <p className="text-body text-[#4B5563]">
                No valid Stripe checkout session identifier was found in the URL.
              </p>
            </div>
            <Button
              type="button"
              variant="primary"
              onClick={handleReturn}
              className="w-full cursor-pointer shadow-saas-sm gap-2"
            >
              <span>Return to Subscription & Billing</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  // State 2: Verification Loading / In-Flight
  if (isVerifying) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
        <div className="max-w-md w-full space-y-6">
          <Card className="p-8 bg-white border border-[#E5E7EB] rounded-2xl shadow-saas-md text-center space-y-6">
            <div className="mx-auto w-16 h-16 bg-[#2563EB]/10 border border-[#2563EB]/20 rounded-full flex items-center justify-center text-[#2563EB]">
              <Loader2 className="w-9 h-9 animate-spin" />
            </div>
            <div className="space-y-2">
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                Verifying with Stripe
              </Badge>
              <h1 className="text-xl font-bold text-[#111827] tracking-tight">
                Verifying Payment Status
              </h1>
              <p className="text-sm text-[#4B5563]">
                Checking cryptographic payment verification with the billing provider...
              </p>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  // State 3: Verification Failed / Invalid Session
  if (isVerifyError || !verifyResult?.verified) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
        <div className="max-w-md w-full space-y-6">
          <Card className="p-8 bg-white border border-[#E5E7EB] rounded-2xl shadow-saas-md text-center space-y-6">
            <div className="mx-auto w-16 h-16 bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-full flex items-center justify-center text-[#EF4444]">
              <ShieldAlert className="w-9 h-9" />
            </div>
            <div className="space-y-2">
              <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                Verification Failed
              </Badge>
              <h1 className="text-2xl font-bold text-[#111827] tracking-tight">
                Payment Not Verified
              </h1>
              <p className="text-body text-[#4B5563]">
                {verifyResult?.message ||
                  'We could not verify a confirmed Stripe payment for this checkout session.'}
              </p>
            </div>
            <div className="flex gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => refetchVerify()}
                className="flex-1 cursor-pointer gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Retry</span>
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={handleReturn}
                className="flex-1 cursor-pointer gap-2"
              >
                <span>Back to Billing</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  // State 4: Verified by Stripe, but Webhook DB sync is still pending
  if (verifyResult.verified && !verifyResult.db_synced) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
        <div className="max-w-md w-full space-y-6">
          <Card className="p-8 bg-white border border-[#E5E7EB] rounded-2xl shadow-saas-md text-center space-y-6">
            <div className="mx-auto w-16 h-16 bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-full flex items-center justify-center text-[#F59E0B]">
              <RefreshCw className="w-9 h-9 animate-spin" />
            </div>
            <div className="space-y-2">
              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                Payment Confirmed · Syncing
              </Badge>
              <h1 className="text-xl font-bold text-[#111827] tracking-tight">
                Activating Your Subscription
              </h1>
              <p className="text-sm text-[#4B5563]">
                Stripe payment confirmed! Your organization features and quota limits are being updated...
              </p>
            </div>
            <div className="p-4 bg-[#F9FAFB] border border-[#E5E7EB] rounded-xl text-left space-y-2 text-xs text-[#4B5563]">
              <div className="flex items-center justify-between">
                <span>Target Plan</span>
                <span className="font-bold text-[#2563EB]">{verifyResult.plan}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Status</span>
                <span className="font-semibold text-[#D97706]">Synchronizing...</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  // State 5: Verified and fully DB Synced
  return (
    <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
      <div className="max-w-md w-full space-y-6">
        <Card className="p-8 bg-white border border-[#E5E7EB] rounded-2xl shadow-saas-md text-center space-y-6">
          <div className="mx-auto w-16 h-16 bg-[#16A34A]/10 border border-[#16A34A]/20 rounded-full flex items-center justify-center text-[#16A34A]">
            <CheckCircle2 className="w-9 h-9" />
          </div>

          <div className="space-y-2">
            <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
              <ShieldCheck className="w-3.5 h-3.5 mr-1" />
              Stripe Payment Verified
            </Badge>
            <h1 className="text-2xl font-bold text-[#111827] tracking-tight">
              Subscription Upgraded!
            </h1>
            <p className="text-body text-[#4B5563]">
              Thank you for your payment. Your organization subscription and quota limits have been updated.
            </p>
          </div>

          <div className="p-4 bg-[#F9FAFB] border border-[#E5E7EB] rounded-xl text-left space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">
                Current Plan Tier
              </span>
              <span className="inline-flex items-center gap-1 text-sm font-bold text-[#2563EB]">
                <Zap className="w-4 h-4 fill-current" />
                {verifyResult.plan || subscription?.plan || org?.plan || 'Enterprise'}
              </span>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-[#E5E7EB]/60 text-xs text-[#4B5563]">
              <span className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-[#6B7280]" />
                Organization
              </span>
              <span className="font-semibold text-[#111827]">{org?.name || 'Your Team'}</span>
            </div>

            {sessionId && (
              <div className="flex items-center justify-between text-xs text-[#4B5563]">
                <span>Stripe Session</span>
                <span className="font-mono text-[11px] text-[#6B7280] truncate max-w-[140px]">
                  {sessionId}
                </span>
              </div>
            )}
          </div>

          <Button
            type="button"
            variant="primary"
            onClick={handleReturn}
            className="w-full cursor-pointer shadow-saas-sm gap-2"
          >
            <span>Return to Subscription & Billing</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        </Card>
      </div>
    </div>
  );
}

export default function PaymentSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
          <div className="text-sm font-medium text-[#4B5563]">Verifying payment status...</div>
        </div>
      }
    >
      <PaymentSuccessContent />
    </Suspense>
  );
}
