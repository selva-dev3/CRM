'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  Check,
  Zap,
  Users,
  HardDrive,
  Bot,
  Crown,
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  useSubscriptionPlansQuery,
  useOrganizationSubscriptionQuery,
  useCreateSubscriptionCheckoutMutation,
  type SubscriptionPlanItem,
} from '@/lib/api/organizations';

function SubscriptionPlansContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orgIdParam = searchParams.get('org_id');

  const [selectedPlanSlug, setSelectedPlanSlug] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    data: plans,
    isLoading: isPlansLoading,
    isError: isPlansError,
    error: plansError,
    refetch: refetchPlans,
  } = useSubscriptionPlansQuery();

  const { data: currentSubscription } = useOrganizationSubscriptionQuery();
  const checkoutMutation = useCreateSubscriptionCheckoutMutation();

  const activePlans = React.useMemo(() => {
    if (!plans || !Array.isArray(plans)) return [];
    return plans.filter((p) => p.is_active !== false);
  }, [plans]);

  const currentPlanName = (currentSubscription?.plan_slug || currentSubscription?.plan || '').toLowerCase();

  const handleSelectPlan = (plan: SubscriptionPlanItem) => {
    if (
      currentPlanName &&
      (plan.slug.toLowerCase() === currentPlanName ||
        plan.name.toLowerCase() === currentPlanName)
    ) {
      return;
    }
    setSelectedPlanSlug(plan.slug);
    setErrorMessage(null);
  };

  const handleBack = () => {
    if (orgIdParam) {
      router.push(`/organization/${encodeURIComponent(orgIdParam)}`);
    } else {
      router.push('/organization');
    }
  };

  const handleUpgrade = async () => {
    if (
      !selectedPlanSlug ||
      (currentPlanName && selectedPlanSlug.toLowerCase() === currentPlanName) ||
      checkoutMutation.isPending ||
      isRedirecting
    ) {
      return;
    }
    try {
      setErrorMessage(null);
      setSuccessMessage(null);
      const res = await checkoutMutation.mutateAsync({
        plan_slug: selectedPlanSlug,
        org_id: orgIdParam || undefined,
      });

      if (res.checkout_url) {
        setIsRedirecting(true);
        setSuccessMessage('Redirecting to Stripe Checkout...');
        window.location.href = res.checkout_url;
      } else {
        throw new Error('No Stripe checkout URL returned.');
      }
    } catch (err: unknown) {
      setIsRedirecting(false);
      const errorObj = err as { response?: { data?: { message?: string } }; message?: string };
      const backendMessage =
        errorObj.response?.data?.message || errorObj.message || 'Failed to initialize Stripe checkout.';
      setErrorMessage(backendMessage);
    }
  };

  const selectedPlan = activePlans.find((p) => p.slug === selectedPlanSlug);

  return (
    <div className="min-h-screen bg-[#F9FAFB] p-4 sm:p-6 lg:p-8 w-full">
      <div className="w-full max-w-[1600px] mx-auto space-y-6 lg:space-y-8">
        {/* HEADER & BACK BUTTON */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <button
              onClick={handleBack}
              className="inline-flex items-center gap-2 text-caption font-semibold text-[#4B5563] hover:text-[#111827] transition-colors cursor-pointer mb-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Organization & Billing</span>
            </button>
            <h1 className="text-heading font-bold text-[#111827] tracking-tight flex items-center gap-3">
              <Crown className="w-7 h-7 text-[#2563EB]" />
              <span>Subscription & Billing Plans</span>
            </h1>
            <p className="text-body text-[#4B5563]">
              Choose the ideal tier for your team to unlock higher seat capacities, MinIO storage limits, and AI assistant capabilities.
            </p>
          </div>
        </div>

        {/* NOTIFICATIONS / FEEDBACK */}
        {successMessage && (
          <div className="p-4 bg-[#16A34A]/10 border border-[#16A34A]/20 rounded-btn flex items-center justify-between gap-3 text-[#16A34A] animate-fadeIn">
            <div className="flex items-center gap-2 font-medium">
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <span>{successMessage}</span>
            </div>
            <Badge className="bg-[#16A34A] text-white border-transparent">Redirecting...</Badge>
          </div>
        )}

        {errorMessage && (
          <div className="p-4 bg-[#DC2626]/10 border border-[#DC2626]/20 rounded-btn flex items-center gap-2 text-[#DC2626] animate-fadeIn">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span className="font-medium">{errorMessage}</span>
          </div>
        )}

        {/* LOADING STATE */}
        {isPlansLoading && (
          <div className="flex flex-col items-center justify-center py-20 bg-white border border-[#E5E7EB] rounded-btn shadow-saas-sm space-y-4">
            <Loader2 className="w-8 h-8 text-[#2563EB] animate-spin" />
            <p className="text-body font-medium text-[#4B5563]">Loading available subscription plans...</p>
          </div>
        )}

        {/* ERROR STATE */}
        {isPlansError && (
          <div className="p-8 bg-white border border-[#DC2626]/20 rounded-btn shadow-saas-sm text-center space-y-4 max-w-lg mx-auto">
            <AlertCircle className="w-10 h-10 text-[#DC2626] mx-auto" />
            <div className="space-y-1">
              <h3 className="text-subheading font-bold text-[#111827]">Failed to Load Plans</h3>
              <p className="text-body text-[#4B5563]">
                {(plansError as Error)?.message || 'Unable to retrieve subscription plan tiers from the backend API.'}
              </p>
            </div>
            <Button
              onClick={() => refetchPlans()}
              variant="outline"
              className="gap-2 cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Retry Loading Plans</span>
            </Button>
          </div>
        )}

        {/* PLANS GRID */}
        {!isPlansLoading && !isPlansError && activePlans.length > 0 && (
          <div className="space-y-6 lg:space-y-8 w-full">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 lg:gap-5 xl:gap-6">
              {activePlans.map((plan) => {
                const isSelected = selectedPlanSlug === plan.slug;
                const isCurrent =
                  Boolean(currentPlanName) &&
                  (currentPlanName === plan.slug.toLowerCase() ||
                    currentPlanName === plan.name.toLowerCase());

                return (
                  <Card
                    key={plan.id || plan.slug}
                    onClick={() => {
                      if (!isCurrent) {
                        handleSelectPlan(plan);
                      }
                    }}
                    className={`relative p-5 rounded-btn transition-all duration-200 flex flex-col justify-between border ${
                      isSelected
                        ? 'border-[#2563EB] ring-2 ring-[#2563EB]/20 bg-white shadow-saas-md scale-[1.02] cursor-pointer'
                        : isCurrent
                        ? 'border-[#16A34A]/40 bg-[#F9FAFB]/60 shadow-saas-sm cursor-default'
                        : 'border-[#E5E7EB] bg-white hover:border-[#2563EB]/40 hover:shadow-saas-sm cursor-pointer'
                    }`}
                  >
                    {/* TOP BADGES */}
                    <div className="flex items-center justify-between mb-3 min-h-[24px]">
                      {isCurrent ? (
                        <Badge className="bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20 text-[11px] font-semibold">
                          Current Plan
                        </Badge>
                      ) : isSelected ? (
                        <Badge className="bg-[#2563EB] text-white border-transparent text-[11px] font-semibold">
                          Selected
                        </Badge>
                      ) : (
                        <span />
                      )}

                      {plan.slug === 'professional' && !isCurrent && !isSelected && (
                        <Badge className="bg-amber-500/10 text-amber-700 border-amber-500/20 text-[11px] font-semibold">
                          Popular
                        </Badge>
                      )}
                    </div>

                    {/* PLAN HEADER */}
                    <div className="space-y-2 mb-4">
                      <h3 className="text-subheading font-bold text-[#111827]">{plan.name}</h3>
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl lg:text-3xl font-extrabold text-[#111827]">
                          ₹{plan.price_monthly.toLocaleString()}
                        </span>
                        <span className="text-caption font-semibold text-[#4B5563]">/mo</span>
                      </div>
                      {plan.price_yearly > 0 && (
                        <div className="text-[11px] text-[#4B5563]">
                          ₹{plan.price_yearly.toLocaleString()} billed yearly
                        </div>
                      )}
                    </div>

                    {/* QUOTAS & LIMITS */}
                    <div className="py-3 border-t border-b border-[#E5E7EB] space-y-2 mb-4 text-[13px] text-[#374151]">
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-[#2563EB] shrink-0" />
                        <span>
                          <strong>{plan.max_users}</strong> User Seats
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <HardDrive className="w-4 h-4 text-purple-600 shrink-0" />
                        <span>
                          <strong>{plan.max_storage_gb} GB</strong> MinIO Storage
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Bot className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>
                          <strong>{plan.ai_credits.toLocaleString()}</strong> AI Credits
                        </span>
                      </div>
                    </div>

                    {/* FEATURES LIST */}
                    <div className="space-y-2 mb-6 flex-1">
                      <div className="text-caption font-bold text-[#4B5563] uppercase tracking-wider text-[11px]">
                        Included Features
                      </div>
                      <ul className="space-y-1.5 text-[12px] text-[#4B5563]">
                        {plan.features && plan.features.length > 0 ? (
                          plan.features.map((feature, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <Check className="w-3.5 h-3.5 text-[#16A34A] shrink-0 mt-0.5" />
                              <span>{feature}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-[#4B5563] italic">Standard CRM features</li>
                        )}
                      </ul>
                    </div>

                    {/* CARD SELECTION BUTTON */}
                    <Button
                      type="button"
                      variant={isSelected ? 'primary' : 'outline'}
                      disabled={isCurrent}
                      className={`w-full font-semibold text-xs h-9 ${
                        isCurrent
                          ? 'border-[#E5E7EB] bg-[#F3F4F6] text-[#9CA3AF] cursor-not-allowed opacity-75'
                          : isSelected
                          ? 'shadow-saas-sm cursor-pointer'
                          : 'border-[#E5E7EB] hover:bg-[#F9FAFB] text-[#374151] cursor-pointer'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!isCurrent) {
                          handleSelectPlan(plan);
                        }
                      }}
                    >
                      {isSelected ? 'Selected' : isCurrent ? 'Active Plan' : `Choose ${plan.name}`}
                    </Button>
                  </Card>
                );
              })}
            </div>

            {/* UPGRADE ACTION BAR */}
            <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="space-y-1 text-center sm:text-left">
                <div className="text-subheading font-bold text-[#111827]">
                  {selectedPlan ? (
                    <span>
                      Selected Tier: <span className="text-[#2563EB]">{selectedPlan.name}</span> (₹{selectedPlan.price_monthly.toLocaleString()}/mo)
                    </span>
                  ) : (
                    <span>Please select a plan above to proceed</span>
                  )}
                </div>
                <p className="text-caption text-[#4B5563]">
                  {selectedPlan
                    ? 'You will be securely redirected to Stripe Checkout to complete payment. Your plan activates automatically upon verification.'
                    : 'Click on any plan card above to review and select your preferred tier.'}
                </p>
              </div>

              <div className="flex items-center gap-3 w-full sm:w-auto">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleBack}
                  disabled={checkoutMutation.isPending || isRedirecting}
                  className="w-full sm:w-auto border-[#E5E7EB] text-[#374151] cursor-pointer"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  onClick={handleUpgrade}
                  disabled={
                    !selectedPlanSlug ||
                    (Boolean(currentPlanName) && selectedPlanSlug.toLowerCase() === currentPlanName) ||
                    checkoutMutation.isPending ||
                    isRedirecting
                  }
                  className="w-full sm:w-auto cursor-pointer shadow-saas-sm gap-2 min-w-[180px]"
                >
                  {checkoutMutation.isPending || isRedirecting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>{isRedirecting ? 'Redirecting to Stripe...' : 'Initializing Checkout...'}</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      <span>{selectedPlan ? `Upgrade to ${selectedPlan.name}` : 'Select a Plan'}</span>
                    </>
                  )}
                </Button>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SubscriptionPlansPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-6">
          <div className="flex items-center gap-3 text-[#4B5563]">
            <Loader2 className="w-6 h-6 animate-spin text-[#2563EB]" />
            <span className="font-medium">Loading subscription plans...</span>
          </div>
        </div>
      }
    >
      <SubscriptionPlansContent />
    </Suspense>
  );
}
