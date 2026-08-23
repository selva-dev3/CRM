'use client';

import React, { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { XCircle, ArrowLeft, RefreshCw, Building2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useCurrentOrganizationQuery } from '@/lib/api/organizations';

function PaymentCancelContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orgId = searchParams.get('org_id');

  const { data: org } = useCurrentOrganizationQuery();

  const handleTryAgain = () => {
    if (orgId) {
      router.push(`/organization/subscription/plans?org_id=${encodeURIComponent(orgId)}`);
    } else {
      router.push('/organization/subscription/plans');
    }
  };

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
          {/* Cancellation Icon */}
          <div className="mx-auto w-16 h-16 bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-full flex items-center justify-center text-[#EF4444]">
            <XCircle className="w-9 h-9" />
          </div>

          <div className="space-y-2">
            <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-200">
              Payment Cancelled
            </Badge>
            <h1 className="text-2xl font-bold text-[#111827] tracking-tight">
              Upgrade Incomplete
            </h1>
            <p className="text-body text-[#4B5563]">
              Your Stripe checkout session was cancelled. No charges were made, and your organization subscription remains unchanged.
            </p>
          </div>

          {/* Details Card */}
          <div className="p-4 bg-[#F9FAFB] border border-[#E5E7EB] rounded-xl text-left space-y-2 text-xs text-[#4B5563]">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium">
                <Building2 className="w-3.5 h-3.5 text-[#6B7280]" />
                Organization
              </span>
              <span className="font-semibold text-[#111827]">{org?.name || 'Your Team'}</span>
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-[#E5E7EB]/60">
              <span>Status</span>
              <span className="font-medium text-[#111827]">Current Plan Intact</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            <Button
              type="button"
              variant="primary"
              onClick={handleTryAgain}
              className="w-full cursor-pointer shadow-saas-sm gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Choose Another Plan</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleReturn}
              className="w-full cursor-pointer border-[#E5E7EB] text-[#374151] gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Organization</span>
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function PaymentCancelPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
          <div className="text-sm font-medium text-[#4B5563]">Loading...</div>
        </div>
      }
    >
      <PaymentCancelContent />
    </Suspense>
  );
}
