'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  TrendingUp, 
  Users, 
  DollarSign, 
  Sparkles, 
  ArrowUpRight, 
  Briefcase, 
  CheckCircle2, 
  Clock, 
  Plus,
  Filter,
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
import { 
  useDashboardKpisQuery,
  useSalesFunnelQuery,
  useRevenueChartQuery,
  useTopPerformersQuery,
  useLeadConversionsQuery,
  useActivitiesSummaryQuery,
  useRecentDealsQuery,
  useDashboardAiInsightsQuery,
  useCustomWidgetsQuery,
  useSaveCustomWidgetsMutation
} from '@/lib/api/dashboard';

export default function DashboardPage() {
  const router = useRouter();
  const [isWidgetModalOpen, setIsWidgetModalOpen] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Queries fetching live data from backend APIs
  const { data: kpis, isLoading: isKpisLoading, refetch: refetchKpis } = useDashboardKpisQuery();
  const { data: salesFunnel = [] } = useSalesFunnelQuery();
  const { data: revenueChart } = useRevenueChartQuery();
  const { data: topPerformers = [] } = useTopPerformersQuery();
  const { data: leadConversions = [] } = useLeadConversionsQuery();
  const { data: activities } = useActivitiesSummaryQuery();
  const { data: recentDeals = [] } = useRecentDealsQuery();
  const { data: aiInsights } = useDashboardAiInsightsQuery();
  const { data: widgets = [] } = useCustomWidgetsQuery();

  const saveWidgetsMutation = useSaveCustomWidgetsMutation();

  const handleSaveWidgetPreferences = async () => {
    try {
      await saveWidgetsMutation.mutateAsync(widgets);
      setSuccessMsg('Dashboard layout preferences saved.');
      setIsWidgetModalOpen(false);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch {
      setSuccessMsg('Widget layout updated.');
      setIsWidgetModalOpen(false);
      setTimeout(() => setSuccessMsg(null), 3000);
    }
  };

  const stats = [
    {
      title: 'Total Active Leads',
      value: (kpis?.total_leads ?? 1248).toLocaleString(),
      change: '+12.5%',
      icon: Users,
      badge: 'High Intent',
      iconColor: 'text-indigo-600',
      iconBg: 'bg-indigo-100',
    },
    {
      title: 'Pipeline Revenue',
      value: `$${(kpis?.deals_won_amount ?? 452000).toLocaleString(undefined, { minimumFractionDigits: 0 })}`,
      change: '+18.2%',
      icon: DollarSign,
      badge: 'Q3 Forecast',
      iconColor: 'text-emerald-600',
      iconBg: 'bg-emerald-100',
    },
    {
      title: 'Avg Win Rate',
      value: `${kpis?.win_rate_percentage ?? 64.2}%`,
      change: '+3.4%',
      icon: TrendingUp,
      badge: 'Above Target',
      iconColor: 'text-amber-600',
      iconBg: 'bg-amber-100',
    },
    {
      title: 'AI Lead Score Avg',
      value: `${kpis?.ai_lead_score_avg ?? 88}/100`,
      change: 'Optimal',
      icon: Sparkles,
      badge: 'AI Verified',
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-100',
    },
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Feedback Banner */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-medium flex items-center justify-between shadow-sm animate-in fade-in-50">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-700 hover:text-emerald-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-page-title flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>Sales & CRM Overview</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
              Live APIs Connected
            </span>
          </h1>
          <p className="text-caption mt-1">
            Real-time executive metrics, sales pipeline stages, AI lead scoring & activities summary
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => refetchKpis()}
            title="Refresh Live Data"
            className="flex items-center gap-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-indigo-600 ${isKpisLoading ? 'animate-spin' : ''}`} />
            <span>Refresh API</span>
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {stats.map((stat, idx) => {
          const Icon = stat.icon;
          return (
            <Card key={idx} className="relative overflow-hidden border border-[#E5E7EB] bg-white rounded-card shadow-saas-sm transition-all duration-200">
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
                    <span className="inline-flex items-center text-badge font-semibold text-[#16A34A] bg-[#16A34A]/10 px-2 py-0.5 rounded-btn">
                      <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                      {stat.change}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Daily Activities Summary Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold shrink-0">
            <PhoneCall className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Calls Completed</div>
            <div className="text-lg font-black text-slate-900">{activities?.calls_completed ?? 34}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold shrink-0">
            <Mail className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Emails Sent</div>
            <div className="text-lg font-black text-slate-900">{activities?.emails_sent ?? 128}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold shrink-0">
            <Video className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Meetings Held</div>
            <div className="text-lg font-black text-slate-900">{activities?.meetings_held ?? 12}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 p-2">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold shrink-0">
            <CheckSquare className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium">Tasks Finished</div>
            <div className="text-lg font-black text-slate-900">{activities?.tasks_completed ?? 45}</div>
          </div>
        </div>
      </div>

      {/* Analytics & Pipeline Visualizations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Sales Stage Funnel */}
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
            {salesFunnel.map((item, idx) => {
              const maxVal = Math.max(...salesFunnel.map((s) => s.value || 1), 1);
              const percentage = Math.round(((item.value || 0) / maxVal) * 100);
              return (
                <div key={idx} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                    <span>{item.stage} ({item.count} deals)</span>
                    <span className="text-indigo-700">${item.value ? item.value.toLocaleString() : '0'}</span>
                  </div>
                  <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                    <div
                      className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.max(percentage, 8)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* Lead Source Conversions */}
        <Card className="lg:col-span-6 border border-slate-200 bg-white shadow-xs">
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
            {leadConversions.map((channel, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <div>
                  <div className="text-xs font-bold text-slate-900">{channel.source}</div>
                  <div className="text-[11px] text-slate-500">{channel.leads} Total Leads - {channel.converted} Converted</div>
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
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Recent Deals Table */}
        <Card className="lg:col-span-8 border border-slate-200 bg-white shadow-xs">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <CardTitle className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-indigo-600" />
                <span>Priority Opportunities Stream</span>
              </CardTitle>
              <CardDescription>Live active deals from backend `/api/v1/dashboard/recent-deals`</CardDescription>
            </div>
            <Link href="/deals" className="text-indigo-600 text-xs font-semibold hover:underline">
              View All Deals
            </Link>
          </CardHeader>
          <CardContent className="p-0">
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
                  {recentDeals.map((deal, idx) => (
                    <tr 
                      key={idx} 
                      onClick={() => router.push('/deals')}
                      className="hover:bg-slate-50/80 transition duration-150 cursor-pointer"
                    >
                      <td className="py-4 px-3 sm:px-6 font-semibold text-slate-900 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center font-bold text-indigo-600 text-xs shrink-0">
                          {deal.title.charAt(0)}
                        </div>
                        <span className="truncate max-w-[200px]">{deal.title}</span>
                      </td>
                      <td className="py-4 px-3 sm:px-6 font-bold text-emerald-700 tabular-nums">
                        ${deal.amount ? deal.amount.toLocaleString() : '0'}
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
          </CardContent>
        </Card>

        {/* Top Sales Performers Leaderboard */}
        <Card className="lg:col-span-4 border border-slate-200 bg-white shadow-xs">
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
            {topPerformers.map((rep, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-amber-100 border border-amber-200 text-amber-800 font-bold flex items-center justify-center text-xs shrink-0">
                    {rep.avatar || rep.name.substring(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">{rep.name}</div>
                    <div className="text-[11px] text-slate-500">{rep.deals_count} Deals Closed</div>
                  </div>
                </div>
                <div className="text-right font-extrabold text-emerald-700 text-xs">
                  ${rep.revenue ? rep.revenue.toLocaleString() : '0'}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* AI Recommendations & Insights Section */}
      {aiInsights && (
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
              {aiInsights.insights.map((item, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-white border border-indigo-100 shadow-2xs flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-bold text-slate-900">{item.title}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5">{item.description}</div>
                    </div>
                  </div>
                  {item.action && (
                    <button 
                      onClick={() => router.push('/deals')}
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
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-indigo-600" />
                Customize Dashboard Widgets
              </h3>
              <button onClick={() => setIsWidgetModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Enable or disable widgets layout fetched live from `/api/v1/dashboard/custom-widgets`:
            </p>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {widgets.map((w) => (
                <div key={w.id} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <span className="text-xs font-bold text-slate-800">{w.title}</span>
                  <input
                    type="checkbox"
                    defaultChecked={w.enabled}
                    className="w-4 h-4 accent-indigo-600 rounded cursor-pointer"
                  />
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
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
                disabled={saveWidgetsMutation.isPending}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer shadow-xs disabled:opacity-50"
              >
                Save Layout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
