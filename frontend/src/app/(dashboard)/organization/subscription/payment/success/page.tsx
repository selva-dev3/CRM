'use client';

import React, { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, ArrowRight, ShieldCheck, Zap, Sparkles, Building2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  useOrganizationSubscriptionQuery,
  useCurrentOrganizationQuery,
} from '@/lib/api/organizations';

function PaymentSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const sessionId = searchParams.get('session_id');
  const orgId = searchParams.get('org_id');

  const { data: subscription, isLoading: isSubscriptionLoading, refetch } =
    useOrganizationSubscriptionQuery();
  const { data: org } = useCurrentOrganizationQuery();

  useEffect(() => {
    // Invalidate queries so fresh subscription state is fetched
    queryClient.invalidateQueries({ queryKey: ['organization-subscription'] });
    queryClient.invalidateQueries({ queryKey: ['current-organization'] });
    queryClient.invalidateQueries({ queryKey: ['organization-usage'] });
    queryClient.invalidateQueries({ queryKey: ['organizations'] });
    refetch();
  }, [queryClient, refetch]);

  const handleReturn = () => {
    if (orgId) {
      router.push(`/organization/${encodeURIComponent(orgId)}`);
    } else if (org?.id) {
      router.push(`/organization/${encodeURIComponent(org.id)}`);
    } else {
      router.push('/organization');
    }
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
      <div className="max-w-md w-full space-y-6">
        <Card className="p-8 bg-white border border-[#E5E7EB] rounded-2xl shadow-saas-md text-center space-y-6">
          {/* Animated Success Icon */}
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

          {/* Subscription Summary Card */}
          <div className="p-4 bg-[#F9FAFB] border border-[#E5E7EB] rounded-xl text-left space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">
                Current Plan Tier
              </span>
              <span className="inline-flex items-center gap-1 text-sm font-bold text-[#2563EB]">
                <Zap className="w-4 h-4 fill-current" />
                {subscription?.plan || org?.plan || 'Enterprise'}
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

          {/* Return Button */}
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
