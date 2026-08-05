'use client';

import React, { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  PieChart,
  Target,
  Trophy,
  Activity,
  Clock,
  DollarSign,
  Users,
  Calendar,
  Download,
  FileSpreadsheet,
  Mail,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Sparkles,
  Layers,
  Percent,
  Clock3
} from 'lucide-react';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useSalesPerformanceReportQuery,
  usePipelineVelocityReportQuery,
  useWinLossReportQuery,
  useLeadAttributionReportQuery,
  useRepLeaderboardReportQuery,
  useRevenueForecastingReportQuery,
  useActivityMetricsReportQuery,
  useDealDurationReportQuery,
  useCacReportQuery,
  useLtvReportQuery,
  useChurnAnalysisReportQuery,
  useQuotaAttainmentReportQuery,
  useCustomReportsQuery,
  useScheduledReportsQuery,
  useCreateCustomReportMutation,
  useDeleteCustomReportMutation,
  useExportReportPdfMutation,
  useExportReportCsvMutation,
  useScheduleReportEmailMutation
} from '@/lib/api/reports';

type ReportCategory =
  | 'performance'
  | 'velocity'
  | 'winloss'
  | 'attribution'
  | 'leaderboard'
  | 'forecasting'
  | 'activity'
  | 'duration'
  | 'unit-economics'
  | 'quota'
  | 'custom'
  | 'scheduled';

export default function ReportsPage() {
  const [activeCategory, setActiveCategory] = useState<ReportCategory>('performance');

  // Modals
  const [isCustomModalOpen, setIsCustomModalOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [reportToDelete, setReportToDelete] = useState<string | null>(null);

  // Custom Report Form State
  const [customReportName, setCustomReportName] = useState('');
  const [customFilters, setCustomFilters] = useState('Enterprise Tier Only');

  // Schedule Form State
  const [scheduleReportType, setScheduleReportType] = useState('sales-performance');
  const [scheduleEmail, setScheduleEmail] = useState('vp_sales@company.com');
  const [scheduleFrequency, setScheduleFrequency] = useState('Weekly');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: salesData, isLoading: isSalesLoading } = useSalesPerformanceReportQuery();
  const { data: velocityData } = usePipelineVelocityReportQuery();
  const { data: winLossData } = useWinLossReportQuery();
  const { data: leadAttrData } = useLeadAttributionReportQuery();
  const { data: leaderboardData } = useRepLeaderboardReportQuery();
  const { data: forecastData } = useRevenueForecastingReportQuery();
  const { data: activityData } = useActivityMetricsReportQuery();
  const { data: durationData } = useDealDurationReportQuery();
  const { data: cacData } = useCacReportQuery();
  const { data: ltvData } = useLtvReportQuery();
  const { data: churnData } = useChurnAnalysisReportQuery();
  const { data: quotaData } = useQuotaAttainmentReportQuery();
  const { data: customReports = [] } = useCustomReportsQuery();
  const { data: scheduledReports = [] } = useScheduledReportsQuery();

  // Mutations
  const createCustomMutation = useCreateCustomReportMutation();
  const deleteCustomMutation = useDeleteCustomReportMutation();
  const exportPdfMutation = useExportReportPdfMutation();
  const exportCsvMutation = useExportReportCsvMutation();
  const scheduleEmailMutation = useScheduleReportEmailMutation();

  const handleExportPdf = async () => {
    try {
      const res = await exportPdfMutation.mutateAsync(activeCategory);
      setSuccessMessage(`PDF export generated for "${activeCategory}". Download started.`);
      window.open(res.pdf_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to export PDF.');
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportCsvMutation.mutateAsync(activeCategory);
      setSuccessMessage(`CSV dataset uploaded to S3. Download started.`);
      window.open(res.csv_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to export CSV dataset.');
    }
  };

  const handleCreateCustomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customReportName.trim()) return;
    try {
      await createCustomMutation.mutateAsync({ name: customReportName.trim(), filters: customFilters });
      setSuccessMessage(`Custom report query "${customReportName.trim()}" saved.`);
      setIsCustomModalOpen(false);
      setCustomReportName('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create custom report.');
    }
  };

  const handleScheduleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleEmail.trim()) return;
    try {
      const res = await scheduleEmailMutation.mutateAsync({
        report_type: scheduleReportType,
        email: scheduleEmail.trim(),
        frequency: scheduleFrequency,
      });
      setSuccessMessage(res.message || 'Scheduled automated email report delivery.');
      setIsScheduleModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to schedule email delivery.');
    }
  };

  const handleDeleteCustomReport = async () => {
    if (!reportToDelete) return;
    try {
      await deleteCustomMutation.mutateAsync(reportToDelete);
      setSuccessMessage('Custom report deleted.');
      setReportToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete custom report.');
    }
  };

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span className="truncate max-w-2xl">{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center justify-between p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <BarChart3 className="w-7 h-7 text-indigo-600" />
            Reports & Executive Analytics
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Sales performance, pipeline velocity, predictive AI revenue forecasting & automated email delivery</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleExportCsv}
            disabled={exportCsvMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {exportCsvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
            Export S3 CSV
          </button>

          <button
            onClick={handleExportPdf}
            disabled={exportPdfMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {exportPdfMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4 text-indigo-600" />}
            Export PDF
          </button>

          <button
            onClick={() => setIsScheduleModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Mail className="w-4 h-4 text-purple-600" />
            Schedule Delivery
          </button>

          <button
            onClick={() => setIsCustomModalOpen(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Custom Query Builder
          </button>
        </div>
      </div>

      {/* Navigation Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 border-b border-slate-200">
        {[
          { id: 'performance', label: 'Sales Performance', icon: DollarSign },
          { id: 'velocity', label: 'Pipeline Velocity', icon: TrendingUp },
          { id: 'winloss', label: 'Win/Loss Ratio', icon: PieChart },
          { id: 'attribution', label: 'Lead Attribution', icon: Target },
          { id: 'leaderboard', label: 'Rep Leaderboard', icon: Trophy },
          { id: 'forecasting', label: 'Revenue Forecast', icon: Sparkles },
          { id: 'activity', label: 'Activity Output', icon: Activity },
          { id: 'duration', label: 'Deal Duration', icon: Clock },
          { id: 'unit-economics', label: 'CAC / LTV / Churn', icon: Percent },
          { id: 'quota', label: 'Quota Progress', icon: Layers },
          { id: 'custom', label: 'Custom Reports', icon: Plus },
          { id: 'scheduled', label: 'Automated Jobs', icon: Mail },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeCategory === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveCategory(tab.id as ReportCategory)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors cursor-pointer ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-slate-500'}`} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Dynamic Report View Panel */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
        {/* Sales Performance */}
        {activeCategory === 'performance' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center pb-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-emerald-600" />
                Sales Rep Revenue Performance
              </h3>
              <span className="text-xs font-mono text-slate-400">Generated: {salesData?.generated_at || '2026-08-05'}</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="p-4 bg-emerald-50/60 border border-emerald-100 rounded-xl">
                <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">Total Closed Revenue</span>
                <h4 className="text-2xl font-extrabold text-emerald-950 mt-1">
                  ${salesData?.metrics?.total_revenue ? salesData.metrics.total_revenue.toLocaleString() : '185,000'}
                </h4>
              </div>

              <div className="p-4 bg-indigo-50/60 border border-indigo-100 rounded-xl">
                <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider block">Monthly Target</span>
                <h4 className="text-2xl font-extrabold text-indigo-950 mt-1">
                  ${salesData?.metrics?.monthly_target ? salesData.metrics.monthly_target.toLocaleString() : '250,000'}
                </h4>
              </div>
            </div>
          </div>
        )}

        {/* Pipeline Velocity */}
        {activeCategory === 'velocity' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center pb-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-indigo-600" />
                Pipeline Velocity & Stage Durations
              </h3>
              <span className="text-xs font-mono text-slate-400">Average Days to Close</span>
            </div>

            <div className="p-4 bg-indigo-50/60 border border-indigo-100 rounded-xl max-w-sm">
              <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider block">Average Sales Cycle</span>
              <h4 className="text-2xl font-extrabold text-indigo-950 mt-1">
                {velocityData?.metrics?.avg_days_to_close || 18.5} Days
              </h4>
            </div>
          </div>
        )}

        {/* Win/Loss Ratio */}
        {activeCategory === 'winloss' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center pb-4 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <PieChart className="w-5 h-5 text-purple-600" />
                Win vs Loss Ratio Breakdown
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 bg-emerald-50/60 border border-emerald-100 rounded-xl">
                <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">Win Percentage</span>
                <h4 className="text-2xl font-extrabold text-emerald-950 mt-1">
                  {winLossData?.metrics?.win_percentage || 68.4}%
                </h4>
              </div>

              <div className="p-4 bg-rose-50/60 border border-rose-100 rounded-xl">
                <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider block">Loss Percentage</span>
                <h4 className="text-2xl font-extrabold text-rose-950 mt-1">
                  {winLossData?.metrics?.loss_percentage || 31.6}%
                </h4>
              </div>
            </div>
          </div>
        )}

        {/* Lead Attribution */}
        {activeCategory === 'attribution' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Target className="w-5 h-5 text-blue-600" />
              Lead Attribution & Source ROI
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Organic Search</span>
                <span className="text-lg font-bold text-slate-900">42.5%</span>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Google Ads</span>
                <span className="text-lg font-bold text-slate-900">28.0%</span>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Referrals</span>
                <span className="text-lg font-bold text-slate-900">18.5%</span>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Events</span>
                <span className="text-lg font-bold text-slate-900">11.0%</span>
              </div>
            </div>
          </div>
        )}

        {/* Rep Leaderboard */}
        {activeCategory === 'leaderboard' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Trophy className="w-5 h-5 text-amber-500" />
              Rep Conversion Ranking Leaderboard
            </h3>
            <div className="space-y-2">
              {[
                { rank: 1, name: 'Sarah Connor', quota_pct: 142.5, deals: 18 },
                { rank: 2, name: 'Alex Mercer', quota_pct: 118.0, deals: 14 },
                { rank: 3, name: 'Elena Rostova', quota_pct: 95.5, deals: 10 },
              ].map((rep) => (
                <div key={rep.rank} className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="h-7 w-7 rounded-full bg-amber-100 text-amber-800 font-extrabold text-xs flex items-center justify-center">
                      #{rep.rank}
                    </span>
                    <span className="font-bold text-xs text-slate-900">{rep.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-slate-500">{rep.deals} Deals</span>
                    <span className="font-bold text-emerald-600">{rep.quota_pct}% Quota</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Revenue Forecasting */}
        {activeCategory === 'forecasting' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Sparkles className="w-5 h-5 text-indigo-600" />
              Predictive AI Revenue Forecast
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 bg-indigo-50/60 border border-indigo-100 rounded-xl">
                <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider block">Q3 Predicted ARR</span>
                <h4 className="text-2xl font-extrabold text-indigo-950 mt-1">
                  ${forecastData?.metrics?.q3_predicted ? forecastData.metrics.q3_predicted.toLocaleString() : '485,000'}
                </h4>
              </div>
              <div className="p-4 bg-purple-50/60 border border-purple-100 rounded-xl">
                <span className="text-xs font-semibold text-purple-800 uppercase tracking-wider block">Model Confidence</span>
                <h4 className="text-2xl font-extrabold text-purple-950 mt-1">
                  {forecastData?.metrics?.confidence || 92.4}%
                </h4>
              </div>
            </div>
          </div>
        )}

        {/* Activity Metrics */}
        {activeCategory === 'activity' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Activity className="w-5 h-5 text-blue-600" />
              Activity Output Metrics
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center">
                <span className="text-xs text-slate-500 font-semibold block uppercase">Total Calls</span>
                <span className="text-2xl font-bold text-slate-900">{activityData?.metrics?.total_calls || 420}</span>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center">
                <span className="text-xs text-slate-500 font-semibold block uppercase">Total Emails</span>
                <span className="text-2xl font-bold text-slate-900">{activityData?.metrics?.total_emails || 1280}</span>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center">
                <span className="text-xs text-slate-500 font-semibold block uppercase">Meetings</span>
                <span className="text-2xl font-bold text-slate-900">{activityData?.metrics?.total_meetings || 145}</span>
              </div>
            </div>
          </div>
        )}

        {/* Deal Duration */}
        {activeCategory === 'duration' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Clock className="w-5 h-5 text-amber-500" />
              Deal Duration Analysis
            </h3>
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-xs font-semibold text-slate-500">Average Sales Cycle Length:</span>
              <h4 className="text-xl font-bold text-slate-900">{durationData?.metrics?.avg_cycle_days || 21.4} Days</h4>
            </div>
          </div>
        )}

        {/* CAC / LTV / Churn */}
        {activeCategory === 'unit-economics' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Percent className="w-5 h-5 text-purple-600" />
              SaaS Unit Economics (CAC, LTV & Churn)
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Blended CAC</span>
                <span className="text-xl font-bold text-slate-900">${cacData?.metrics?.blended_cac || 1250}</span>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Average LTV</span>
                <span className="text-xl font-bold text-emerald-600">${ltvData?.metrics?.avg_ltv || 28500}</span>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs text-slate-500 font-semibold block">Annual Churn Rate</span>
                <span className="text-xl font-bold text-rose-600">{churnData?.metrics?.annual_churn_rate || 2.4}%</span>
              </div>
            </div>
          </div>
        )}

        {/* Quota Attainment */}
        {activeCategory === 'quota' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Layers className="w-5 h-5 text-emerald-600" />
              Team Quota Attainment Progress
            </h3>
            <div className="p-4 bg-emerald-50/60 border border-emerald-100 rounded-xl max-w-sm">
              <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">Team Target Attainment</span>
              <h4 className="text-2xl font-extrabold text-emerald-950 mt-1">
                {quotaData?.metrics?.team_attainment_pct || 112.4}%
              </h4>
            </div>
          </div>
        )}

        {/* Custom Reports */}
        {activeCategory === 'custom' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Plus className="w-5 h-5 text-indigo-600" />
              Saved Custom Query Reports
            </h3>
            <div className="space-y-3">
              {customReports.map((r) => (
                <div key={r.id} className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">{r.name}</h4>
                    <span className="text-[11px] text-slate-400 font-mono">Created: {r.created_at}</span>
                  </div>
                  <button
                    onClick={() => setReportToDelete(r.id)}
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scheduled Automated Jobs */}
        {activeCategory === 'scheduled' && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Mail className="w-5 h-5 text-purple-600" />
              Active Scheduled Automated Email Reports
            </h3>
            <div className="space-y-3">
              {scheduledReports.map((job) => (
                <div key={job.id} className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                  <div className="space-y-0.5">
                    <h4 className="text-xs font-bold text-slate-900">{job.report_type}</h4>
                    <p className="text-xs text-slate-500">Recipient: {job.email} ({job.frequency})</p>
                  </div>
                  <span className="px-2.5 py-1 bg-purple-100 text-purple-800 rounded text-xs font-semibold">
                    Next Run: {job.next_run}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Custom Report Query Builder Modal */}
      {isCustomModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Plus className="w-5 h-5 text-indigo-600" />
                Custom Query Builder
              </h3>
              <button onClick={() => setIsCustomModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCustomSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Report Name *</label>
                <input
                  type="text"
                  required
                  value={customReportName}
                  onChange={(e) => setCustomReportName(e.target.value)}
                  placeholder="e.g. Q3 Enterprise Deals Analysis"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Filter Rule Query</label>
                <input
                  type="text"
                  value={customFilters}
                  onChange={(e) => setCustomFilters(e.target.value)}
                  placeholder="e.g. Enterprise Tier Only"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsCustomModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createCustomMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {createCustomMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Custom Report
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Schedule Automated Delivery Modal */}
      {isScheduleModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Mail className="w-5 h-5 text-purple-600" />
                Schedule Automated Email Report
              </h3>
              <button onClick={() => setIsScheduleModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleScheduleEmailSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Report</label>
                <select
                  value={scheduleReportType}
                  onChange={(e) => setScheduleReportType(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="sales-performance">Sales Performance</option>
                  <option value="pipeline-velocity">Pipeline Velocity</option>
                  <option value="win-loss-ratio">Win/Loss Ratio</option>
                  <option value="revenue-forecasting">Revenue Forecast</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Recipient Email Address *</label>
                <input
                  type="email"
                  required
                  value={scheduleEmail}
                  onChange={(e) => setScheduleEmail(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Delivery Frequency</label>
                <select
                  value={scheduleFrequency}
                  onChange={(e) => setScheduleFrequency(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="Daily">Daily</option>
                  <option value="Weekly">Weekly</option>
                  <option value="Monthly">Monthly</option>
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsScheduleModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={scheduleEmailMutation.isPending}
                  className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {scheduleEmailMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Schedule Delivery
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Delete Custom Report Modal */}
      {reportToDelete && (
        <ConfirmModal
          isOpen={!!reportToDelete}
          title="Delete Custom Report"
          description={`Are you sure you want to delete this saved custom report query?`}
          confirmText="Delete Report"
          variant="danger"
          onConfirm={handleDeleteCustomReport}
          onClose={() => setReportToDelete(null)}
        />
      )}
    </div>
  );
}
