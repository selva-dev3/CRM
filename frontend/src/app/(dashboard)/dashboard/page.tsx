'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  TrendingUp, 
  Users, 
  DollarSign, 
  Sparkles, 
  Briefcase, 
  CheckCircle2, 
  Plus,
  BarChart3,
  PieChart,
  PhoneCall,
  Mail,
  Video,
  CheckSquare,
  Trophy,
  SlidersHorizontal,
  RefreshCw,
  X,
  AlertCircle
} from 'lucide-react';
import { Button, Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui';
import { ModalShell } from '@/components/common/modal-shell';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';
import { 
  useDashboardKpisQuery,
  useSalesFunnelQuery,
  useTopPerformersQuery,
  useLeadConversionsQuery,
  useActivitiesSummaryQuery,
  useRecentDealsQuery,
  useDashboardAiInsightsQuery,
  useCustomWidgetsQuery,
  useSaveCustomWidgetsMutation,
  DEFAULT_DASHBOARD_CURRENCY,
  DEFAULT_DASHBOARD_LOCALE,
  type CustomWidget
} from '@/lib/api/dashboard';

function DashboardSectionError({
  message,
  onRetry,
  className = '',
}: {
  message: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-6 text-center ${className}`}>
      <AlertCircle className="h-5 w-5 text-rose-600" />
      <p className="text-sm font-medium text-rose-900">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"
      >
        Try again
      </button>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { hasPermission } = useHasPermission();
  const canGenerateAi = hasPermission(PERMISSIONS.AI.GENERATE);
  const [isWidgetModalOpen, setIsWidgetModalOpen] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [widgetPreferences, setWidgetPreferences] = useState<CustomWidget[] | null>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Queries fetching live data from backend APIs
  const kpisQuery = useDashboardKpisQuery();
  const salesFunnelQuery = useSalesFunnelQuery();
  const topPerformersQuery = useTopPerformersQuery();
  const leadConversionsQuery = useLeadConversionsQuery();
  const activitiesQuery = useActivitiesSummaryQuery();
  const recentDealsQuery = useRecentDealsQuery();
  const aiInsightsQuery = useDashboardAiInsightsQuery({ enabled: canGenerateAi });
  const widgetsQuery = useCustomWidgetsQuery();

  const { data: kpis } = kpisQuery;
  const salesFunnel = salesFunnelQuery.data ?? [];
  const maxFunnelValue = Math.max(...salesFunnel.map((stage) => stage.value), 0);
  const topPerformers = topPerformersQuery.data ?? [];
  const leadConversions = leadConversionsQuery.data ?? [];
  const activities = activitiesQuery.data;
  const recentDeals = recentDealsQuery.data ?? [];
  const aiInsights = aiInsightsQuery.data;
  const widgets = widgetsQuery.data ?? [];

  const currencyFormatter = useMemo(() => {
    return new Intl.NumberFormat(kpis?.locale ?? DEFAULT_DASHBOARD_LOCALE, {
      style: 'currency',
      currency: kpis?.currency ?? DEFAULT_DASHBOARD_CURRENCY,
      maximumFractionDigits: 0,
    });
  }, [kpis]);

  const formatCurrency = (value: number) => currencyFormatter.format(value);

  const saveWidgetsMutation = useSaveCustomWidgetsMutation();

  useEffect(() => () => {
    if (successTimerRef.current) clearTimeout(successTimerRef.current);
  }, []);

  const dismissSuccessMessage = () => {
    if (successTimerRef.current) {
      clearTimeout(successTimerRef.current);
      successTimerRef.current = null;
    }
    setSuccessMsg(null);
  };

  const handleRefreshDashboard = async () => {
    const refreshes: Promise<unknown>[] = [
      kpisQuery.refetch(),
      salesFunnelQuery.refetch(),
      topPerformersQuery.refetch(),
      leadConversionsQuery.refetch(),
      activitiesQuery.refetch(),
      recentDealsQuery.refetch(),
    ];
    if (canGenerateAi) refreshes.push(aiInsightsQuery.refetch());
    await Promise.all(refreshes);
  };

  const handleSaveWidgetPreferences = async () => {
    try {
      await saveWidgetsMutation.mutateAsync(widgetPreferences ?? widgets);
      await widgetsQuery.refetch();
      setErrorMsg(null);
      setSuccessMsg('Dashboard layout preferences saved.');
      setIsWidgetModalOpen(false);
      if (successTimerRef.current) clearTimeout(successTimerRef.current);
      successTimerRef.current = setTimeout(() => {
        setSuccessMsg(null);
        successTimerRef.current = null;
      }, 3000);
    } catch {
      setSuccessMsg(null);
      setErrorMsg('Dashboard layout could not be saved. Please try again.');
    }
  };

  const stats = kpis ? [
    {
      title: 'Total Active Leads',
      value: kpis.total_leads.toLocaleString(),
      context: 'Current active leads',
      icon: Users,
      badge: 'Active',
      iconColor: 'text-indigo-600',
      iconBg: 'bg-indigo-100',
      contextColor: 'text-slate-600 bg-slate-100',
    },
    {
      title: 'Pipeline Revenue',
      value: formatCurrency(kpis.pipeline_revenue),
      context: 'Open opportunities',
      icon: DollarSign,
      badge: 'Open Pipeline',
      iconColor: 'text-emerald-600',
      iconBg: 'bg-emerald-100',
      contextColor: 'text-slate-600 bg-slate-100',
    },
    {
      title: 'Avg Win Rate',
      value: kpis.closed_deals_count > 0 ? `${kpis.win_rate_percentage}%` : '—',
      context: kpis.closed_deals_count > 0
        ? `${kpis.won_deals_count} of ${kpis.closed_deals_count} closed won`
        : 'No closed deals yet',
      icon: TrendingUp,
      badge: 'Closed Deals',
      iconColor: 'text-amber-600',
      iconBg: 'bg-amber-100',
      contextColor: 'text-slate-600 bg-slate-100',
    },
    {
      title: 'AI Lead Score Avg',
      value: kpis.scored_leads_count > 0 ? `${kpis.ai_lead_score_avg}/100` : '—',
      context: kpis.scored_leads_count > 0
        ? `Across ${kpis.scored_leads_count} scored leads`
        : 'No scored leads yet',
      icon: Sparkles,
      badge: kpis.scored_leads_count === 0
        ? 'Not Scored'
        : kpis.ai_lead_score_avg >= 70
          ? 'Strong'
          : 'Needs Attention',
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-100',
      contextColor: kpis.scored_leads_count > 0 && kpis.ai_lead_score_avg < 70
        ? 'text-amber-800 bg-amber-100'
        : 'text-slate-600 bg-slate-100',
    },
  ] : [];

  const isWidgetEnabled = (id: string) => (
    widgets.find((widget) => widget.id === id)?.enabled !== false
  );
  const showKpis = isWidgetEnabled('w-kpis');
  const showFunnel = isWidgetEnabled('w-funnel');
  const showTopPerformers = isWidgetEnabled('w-top');
  const showRecentDeals = isWidgetEnabled('w-deals');
  const showAiInsights = canGenerateAi && isWidgetEnabled('w-ai');

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Feedback Banner */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-medium flex items-center justify-between shadow-sm animate-in fade-in-50">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button
            type="button"
            onClick={dismissSuccessMessage}
            className="rounded p-1 text-emerald-700 hover:text-emerald-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            aria-label="Dismiss success message"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {errorMsg && (
        <div role="alert" className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm font-medium flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMsg(null)}
            className="p-1 text-rose-700 hover:text-rose-900 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-page-title flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>Sales & CRM Overview</span>
          </h1>
          <p className="text-caption mt-1">
            Executive metrics, sales pipeline stages, lead scoring, and today&apos;s activities
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleRefreshDashboard}
            title="Refresh dashboard data"
            disabled={kpisQuery.isFetching}
            className="flex items-center gap-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-indigo-600 ${kpisQuery.isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh Dashboard</span>
          </button>
          
          <button
            onClick={() => setIsWidgetModalOpen(true)}
            className="flex items-center gap-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-slate-600" />
            <span>Customize Widgets</span>
          </button>

          <Button size="default" variant="primary" onClick={() => router.push('/deals')} className="shadow-saas-sm cursor-pointer">
            <Plus className="w-4 h-4 mr-2" />
            <span>New Deal</span>
          </Button>
        </div>
      </div>

      {/* Executive Metric Cards Grid */}
      {showKpis && (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {kpisQuery.isLoading && Array.from({ length: 4 }).map((_, idx) => (
          <Card key={idx} className="h-[150px] animate-pulse bg-slate-100" aria-hidden="true" />
        ))}
        {kpisQuery.isError && (
          <DashboardSectionError
            className="sm:col-span-2 lg:col-span-4"
            message="Executive metrics could not be loaded."
            onRetry={() => void kpisQuery.refetch()}
          />
        )}
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.title} className="relative overflow-hidden border border-[#E5E7EB] bg-white rounded-card shadow-saas-sm transition-all duration-200">
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div className={`w-10 h-10 rounded-btn ${stat.iconBg} flex items-center justify-center ${stat.iconColor}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-badge font-semibold px-2.5 py-0.5 rounded-full bg-[#F3F4F6] text-[#374151] border border-[#E5E7EB]">
                    {stat.badge}
                  </span>
                </div>
                <div className="mt-4">
                  <p className="text-caption font-semibold uppercase tracking-wider text-[#6B7280]">
                    {stat.title}
                  </p>
                  <div className="flex items-baseline justify-between mt-1">
                    <h3 className="text-section-title">
                      {stat.value}
                    </h3>
                    <span className={`inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded-btn ${stat.contextColor}`}>
                      {stat.context}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
      )}

      {/* Daily Activities Summary Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between px-2 pb-2">
          <h2 className="text-sm font-bold text-slate-900">Activity Summary</h2>
          <span className="text-xs font-medium text-slate-600">{activities?.period_label ?? 'Today'}</span>
        </div>
        {activitiesQuery.isLoading && (
          <div className="h-16 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
        )}
        {activitiesQuery.isError && (
          <DashboardSectionError
            message="Today’s activity summary could not be loaded."
            onRetry={() => void activitiesQuery.refetch()}
          />
        )}
        {activities && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold shrink-0">
            <PhoneCall className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-600 font-medium">Calls Completed</div>
            <div className="text-lg font-black text-slate-900">{activities.calls_completed}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold shrink-0">
            <Mail className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-600 font-medium">Emails Sent</div>
            <div className="text-lg font-black text-slate-900">{activities.emails_sent}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold shrink-0">
            <Video className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-600 font-medium">Meetings Held</div>
            <div className="text-lg font-black text-slate-900">{activities.meetings_held}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold shrink-0">
            <CheckSquare className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-600 font-medium">Tasks Finished</div>
            <div className="text-lg font-black text-slate-900">{activities.tasks_completed}</div>
          </div>
        </div>
        </div>
        )}
      </div>

      {/* Analytics & Pipeline Visualizations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Sales Stage Funnel */}
        {showFunnel && (
        <Card className="lg:col-span-6 border border-slate-200 bg-white shadow-xs">
          <CardHeader className="pb-3 border-b border-slate-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-600" />
                <div>
                  <CardTitle className="text-base font-bold text-slate-900">Sales Stage Funnel</CardTitle>
                  <CardDescription className="text-xs text-slate-500">Live conversion pipeline distribution</CardDescription>
                </div>
              </div>
              <Link href="/deals" className="text-xs font-semibold text-indigo-600 hover:underline">
                View Deals
              </Link>
            </div>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            {salesFunnelQuery.isLoading && (
              <div className="h-48 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
            )}
            {salesFunnelQuery.isError && (
              <DashboardSectionError
                message="The sales funnel could not be loaded."
                onRetry={() => void salesFunnelQuery.refetch()}
              />
            )}
            {!salesFunnelQuery.isLoading && !salesFunnelQuery.isError && salesFunnel.length === 0 && (
              <p className="py-12 text-center text-sm text-slate-600">No deals are available yet.</p>
            )}
            {salesFunnel.map((item) => {
              const percentage = maxFunnelValue > 0
                ? Math.round((item.value / maxFunnelValue) * 100)
                : 0;
              return (
                <div key={item.stage} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                    <span>{item.stage} ({item.count} deals)</span>
                    <span className="text-indigo-700">{formatCurrency(item.value)}</span>
                  </div>
                  <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                    <div
                      className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                      role="progressbar"
                      aria-label={`${item.stage} pipeline value`}
                      aria-valuemin={0}
                      aria-valuemax={maxFunnelValue}
                      aria-valuenow={item.value}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
        )}

        {/* Lead Source Conversions */}
        <Card className={`${showFunnel ? 'lg:col-span-6' : 'lg:col-span-12'} border border-slate-200 bg-white shadow-xs`}>
          <CardHeader className="pb-3 border-b border-slate-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PieChart className="w-5 h-5 text-emerald-600" />
                <div>
                  <CardTitle className="text-base font-bold text-slate-900">Lead Channel Distribution</CardTitle>
                  <CardDescription className="text-xs text-slate-500">Inbound source volume & conversion rate</CardDescription>
                </div>
              </div>
              <Link href="/leads" className="text-xs font-semibold text-indigo-600 hover:underline">
                View Leads
              </Link>
            </div>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            {leadConversionsQuery.isLoading && (
              <div className="h-48 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
            )}
            {leadConversionsQuery.isError && (
              <DashboardSectionError
                message="Lead channel data could not be loaded."
                onRetry={() => void leadConversionsQuery.refetch()}
              />
            )}
            {!leadConversionsQuery.isLoading && !leadConversionsQuery.isError && leadConversions.length === 0 && (
              <p className="py-12 text-center text-sm text-slate-600">No lead-source data is available yet.</p>
            )}
            {leadConversions.map((channel) => (
              <div key={channel.source} className="flex items-center justify-between gap-3 p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <div>
                  <div className="text-xs font-bold text-slate-900">{channel.source}</div>
                  <div className="text-xs text-slate-600">{channel.leads} total leads · {channel.converted} converted</div>
                </div>
                <div className="text-right">
                  <span className="px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-extrabold border border-emerald-200">
                    {channel.rate}% Conv
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid: Recent Opportunities & Top Performers */}
      {(showRecentDeals || showTopPerformers) && (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Recent Deals Table */}
        {showRecentDeals && (
        <Card className={`${showTopPerformers ? 'lg:col-span-8' : 'lg:col-span-12'} border border-slate-200 bg-white shadow-xs`}>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <CardTitle className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-indigo-600" />
                <span>Priority Opportunities Stream</span>
              </CardTitle>
              <CardDescription>Recently updated opportunities requiring attention</CardDescription>
            </div>
            <Link href="/deals" className="text-indigo-600 text-xs font-semibold hover:underline">
              View All Deals
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {recentDealsQuery.isLoading && (
              <div className="m-5 h-48 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
            )}
            {recentDealsQuery.isError && (
              <DashboardSectionError
                className="m-5"
                message="Recent opportunities could not be loaded."
                onRetry={() => void recentDealsQuery.refetch()}
              />
            )}
            {!recentDealsQuery.isLoading && !recentDealsQuery.isError && recentDeals.length === 0 && (
              <p className="p-12 text-center text-sm text-slate-600">No opportunities are available yet.</p>
            )}
            {recentDeals.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3 px-3 sm:px-6">Opportunity Title</th>
                    <th className="py-3 px-3 sm:px-6">Value</th>
                    <th className="py-3 px-3 sm:px-6">Stage</th>
                    <th className="py-3 px-3 sm:px-6">Sales Rep</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentDeals.map((deal) => (
                    <tr
                      key={deal.deal_id}
                      className="hover:bg-slate-50/80 transition duration-150"
                    >
                      <td className="py-4 px-3 sm:px-6 font-semibold text-slate-900 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center font-bold text-indigo-600 text-xs shrink-0">
                          {deal.title.charAt(0)}
                        </div>
                        <Link
                          href={`/deals/${deal.deal_id}`}
                          className="truncate max-w-[200px] rounded text-indigo-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                        >
                          {deal.title}
                        </Link>
                      </td>
                      <td className="py-4 px-3 sm:px-6 font-bold text-emerald-700 tabular-nums">
                        {formatCurrency(deal.amount)}
                      </td>
                      <td className="py-4 px-3 sm:px-6">
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
                          {deal.stage || 'In Pipeline'}
                        </span>
                      </td>
                      <td className="py-4 px-3 sm:px-6 text-slate-600 text-xs font-medium">
                        {deal.owner || 'Selva Admin'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
          </CardContent>
        </Card>
        )}

        {/* Top Sales Performers Leaderboard */}
        {showTopPerformers && (
        <Card className={`${showRecentDeals ? 'lg:col-span-4' : 'lg:col-span-12'} border border-slate-200 bg-white shadow-xs`}>
          <CardHeader className="pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-500" />
              <div>
                <CardTitle className="text-base font-bold text-slate-900">Top Sales Leaderboard</CardTitle>
                <CardDescription className="text-xs text-slate-500">Highest deal volume & revenue contributors</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {topPerformersQuery.isLoading && (
              <div className="h-48 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
            )}
            {topPerformersQuery.isError && (
              <DashboardSectionError
                message="The sales leaderboard could not be loaded."
                onRetry={() => void topPerformersQuery.refetch()}
              />
            )}
            {!topPerformersQuery.isLoading && !topPerformersQuery.isError && topPerformers.length === 0 && (
              <p className="py-12 text-center text-sm text-slate-600">No closed-won sales are available yet.</p>
            )}
            {topPerformers.map((rep) => (
              <div key={rep.name} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-amber-100 border border-amber-200 text-amber-800 font-bold flex items-center justify-center text-xs shrink-0">
                    {rep.avatar || rep.name.substring(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">{rep.name}</div>
                    <div className="text-xs text-slate-600">{rep.deals_count} deals won</div>
                  </div>
                </div>
                <div className="text-right font-extrabold text-emerald-700 text-xs">
                  {formatCurrency(rep.revenue)}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        )}
      </div>
      )}

      {/* AI Recommendations & Insights Section */}
      {showAiInsights && aiInsightsQuery.isLoading && (
        <Card className="h-36 animate-pulse bg-slate-100" aria-hidden="true" />
      )}
      {showAiInsights && aiInsightsQuery.isError && (
        <DashboardSectionError
          message="AI pipeline insights could not be loaded."
          onRetry={() => void aiInsightsQuery.refetch()}
        />
      )}
      {showAiInsights && aiInsights && (
        <Card className="border border-indigo-100 bg-gradient-to-r from-indigo-50/60 via-white to-purple-50/40 shadow-xs p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-600 text-white shadow-sm shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900">AI Executive Pipeline Briefing</h3>
                <p className="text-xs text-slate-600 font-medium max-w-3xl">{aiInsights.summary}</p>
              </div>
            </div>
            <Button variant="outline" onClick={() => router.push('/reports')} className="text-xs font-semibold border-indigo-200 text-indigo-700 hover:bg-indigo-50 shrink-0">
              Generate Detailed Report
            </Button>
          </div>

          {aiInsights.insights && aiInsights.insights.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 pt-4 border-t border-indigo-100">
              {aiInsights.insights.map((item) => (
                <div key={item.title} className="p-3.5 rounded-xl bg-white border border-indigo-100 shadow-2xs flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-bold text-slate-900">{item.title}</div>
                      <div className="text-xs text-slate-600 mt-0.5">{item.description}</div>
                    </div>
                  </div>
                  {item.action && (
                    <button 
                      onClick={() => router.push(item.deal_id ? `/deals/${item.deal_id}` : '/deals')}
                      className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[11px] font-bold rounded-lg transition shrink-0"
                    >
                      {item.action}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* CUSTOM WIDGETS LAYOUT MODAL */}
      {isWidgetModalOpen && (
        <ModalShell
          isOpen={isWidgetModalOpen}
          onClose={() => setIsWidgetModalOpen(false)}
          size="md"
          title={
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-indigo-600" />
              Customize Dashboard Widgets
            </h3>
          }
        >
          <p className="text-xs text-slate-500">
            Choose which dashboard sections should be visible.
          </p>

          <div className="space-y-2 max-h-60 overflow-y-auto mt-4">
            {widgetsQuery.isLoading && (
              <div className="h-24 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
            )}
            {widgetsQuery.isError && (
              <DashboardSectionError
                message="Widget preferences could not be loaded."
                onRetry={() => void widgetsQuery.refetch()}
              />
            )}
            {!widgetsQuery.isLoading && !widgetsQuery.isError && (widgetPreferences ?? widgets).length === 0 && (
              <p className="py-8 text-center text-sm text-slate-600">No configurable widgets are available.</p>
            )}
            {(widgetPreferences ?? widgets).map((w) => (
              <div key={w.id} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <label htmlFor={`widget-${w.id}`} className="text-xs font-bold text-slate-800">{w.title}</label>
                <input
                  id={`widget-${w.id}`}
                  type="checkbox"
                  checked={w.enabled}
                  onChange={(event) => {
                    setWidgetPreferences((current) => (current ?? widgets).map((widget) => (
                      widget.id === w.id ? { ...widget, enabled: event.target.checked } : widget
                    )));
                  }}
                  className="w-4 h-4 accent-indigo-600 rounded cursor-pointer"
                />
              </div>
            ))}
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-3 border-t border-slate-100 mt-4">
            <button
              type="button"
              onClick={() => setIsWidgetModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveWidgetPreferences}
              disabled={saveWidgetsMutation.isPending || widgetsQuery.isLoading || widgetsQuery.isError}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer shadow-xs disabled:opacity-50"
            >
              {saveWidgetsMutation.isPending ? 'Saving…' : 'Save Layout'}
            </button>
          </div>
        </ModalShell>
      )}
    </div>
  );
}
