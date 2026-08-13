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
  Filter
} from 'lucide-react';
import { DataTable, DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
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
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [isCustomModalOpen, setIsCustomModalOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [reportToDelete, setReportToDelete] = useState<string | null>(null);

  // Form States
  const [customReportName, setCustomReportName] = useState('');
  const [customFilters, setCustomFilters] = useState('Enterprise Accounts Only');
  const [scheduleReportType, setScheduleReportType] = useState('sales-performance');
  const [scheduleEmail, setScheduleEmail] = useState('vp_sales@company.com');
  const [scheduleFrequency, setScheduleFrequency] = useState('Weekly');

  // Notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // API Queries
  const { data: salesData, isLoading: isSalesLoading } = useSalesPerformanceReportQuery();
  const { data: velocityData, isLoading: isVelocityLoading } = usePipelineVelocityReportQuery();
  const { data: winLossData, isLoading: isWinLossLoading } = useWinLossReportQuery();
  const { data: leadAttrData, isLoading: isLeadAttrLoading } = useLeadAttributionReportQuery();
  const { data: leaderboardData, isLoading: isLeaderboardLoading } = useRepLeaderboardReportQuery();
  const { data: forecastData, isLoading: isForecastLoading } = useRevenueForecastingReportQuery();
  const { data: activityData, isLoading: isActivityLoading } = useActivityMetricsReportQuery();
  const { data: durationData, isLoading: isDurationLoading } = useDealDurationReportQuery();
  const { data: cacData, isLoading: isCacLoading } = useCacReportQuery();
  const { data: ltvData } = useLtvReportQuery();
  const { data: churnData } = useChurnAnalysisReportQuery();
  const { data: quotaData, isLoading: isQuotaLoading } = useQuotaAttainmentReportQuery();
  const { data: customReports = [], isLoading: isCustomLoading } = useCustomReportsQuery();
  const { data: scheduledReports = [], isLoading: isScheduledLoading } = useScheduledReportsQuery();

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
      setSuccessMessage(`CSV dataset uploaded to S3 bucket. Download started.`);
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
      setSuccessMessage('Custom report query deleted.');
      setReportToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete custom report.');
    }
  };

  // Helper search filter
  const filterRows = (rows: any[], keys: string[]) => {
    if (!searchQuery.trim()) return rows;
    const query = searchQuery.toLowerCase().trim();
    return rows.filter((r) => keys.some((k) => String(r[k] || '').toLowerCase().includes(query)));
  };

  // Column Definitions
  const performanceColumns: DataTableColumn<any>[] = [
    { id: 'rep_name', header: 'Sales Executive', cell: (row) => <span className="font-bold text-slate-900">{row.rep_name}</span> },
    { id: 'role', header: 'Role', cell: (row) => <span className="text-slate-500">{row.role}</span> },
    { id: 'deals_assigned', header: 'Assigned', className: 'text-center', cell: (row) => <span className="font-semibold">{row.deals_assigned}</span> },
    { id: 'deals_closed', header: 'Closed', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-700">{row.deals_closed}</span> },
    { id: 'win_rate', header: 'Win Rate (%)', className: 'text-center', cell: (row) => <span className="font-bold">{row.win_rate}%</span> },
    { id: 'revenue', header: 'Revenue ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.revenue?.toLocaleString()}</span> },
    { id: 'quota_target', header: 'Quota ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">${row.quota_target?.toLocaleString()}</span> },
    {
      id: 'attainment_pct',
      header: 'Attainment Progress',
      className: 'text-center',
      cell: (row) => (
        <div className="flex items-center gap-2 justify-center">
          <div className="w-20 bg-slate-200 h-2 rounded-full overflow-hidden">
            <div className={`h-full ${row.attainment_pct >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${Math.min(100, row.attainment_pct)}%` }} />
          </div>
          <span className="font-bold text-[11px]">{row.attainment_pct}%</span>
        </div>
      )
    },
    { id: 'avg_deal_size', header: 'Avg Deal Size ($)', className: 'text-right', cell: (row) => <span className="font-mono">${row.avg_deal_size?.toLocaleString()}</span> }
  ];

  const velocityColumns: DataTableColumn<any>[] = [
    { id: 'stage', header: 'Pipeline Stage', cell: (row) => <span className="font-bold text-slate-900">{row.stage}</span> },
    { id: 'deal_count', header: 'Active Deals', className: 'text-center', cell: (row) => <span className="font-semibold">{row.deal_count}</span> },
    { id: 'total_value', header: 'Stage Value ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.total_value?.toLocaleString()}</span> },
    { id: 'avg_days_in_stage', header: 'Avg Days in Stage', className: 'text-center', cell: (row) => <span className="font-bold text-indigo-600">{row.avg_days_in_stage} Days</span> },
    { id: 'conversion_rate', header: 'Conversion Rate (%)', className: 'text-center', cell: (row) => <span className="font-bold">{row.conversion_rate}%</span> },
    {
      id: 'bottleneck_risk',
      header: 'Bottleneck Risk',
      className: 'text-center',
      cell: (row) => (
        <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${row.bottleneck_risk === 'Low' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
          {row.bottleneck_risk}
        </span>
      )
    }
  ];

  const winLossColumns: DataTableColumn<any>[] = [
    { id: 'segment', header: 'Market Industry Segment', cell: (row) => <span className="font-bold text-slate-900">{row.segment}</span> },
    { id: 'won_deals', header: 'Won Deals', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.won_deals}</span> },
    { id: 'lost_deals', header: 'Lost Deals', className: 'text-center', cell: (row) => <span className="font-bold text-rose-600">{row.lost_deals}</span> },
    { id: 'total_deals', header: 'Total Deals', className: 'text-center', cell: (row) => <span className="font-semibold">{row.total_deals}</span> },
    { id: 'win_percentage', header: 'Win Rate (%)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.win_percentage}%</span> },
    { id: 'won_value', header: 'Won Revenue ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.won_value?.toLocaleString()}</span> },
    { id: 'lost_value', header: 'Lost Opportunity ($)', className: 'text-right', cell: (row) => <span className="font-mono text-rose-500">${row.lost_value?.toLocaleString()}</span> },
    { id: 'primary_loss_reason', header: 'Primary Loss Reason', cell: (row) => <span className="text-slate-600">{row.primary_loss_reason}</span> }
  ];

  const leadAttrColumns: DataTableColumn<any>[] = [
    { id: 'source', header: 'Lead Source Channel', cell: (row) => <span className="font-bold text-slate-900">{row.source}</span> },
    { id: 'total_leads', header: 'Total Leads', className: 'text-center', cell: (row) => <span className="font-semibold">{row.total_leads}</span> },
    { id: 'converted_leads', header: 'Converted Leads', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.converted_leads}</span> },
    { id: 'conversion_rate', header: 'Conversion Rate (%)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.conversion_rate}%</span> },
    { id: 'revenue_generated', header: 'Revenue Generated ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.revenue_generated?.toLocaleString()}</span> },
    { id: 'avg_lead_score', header: 'Avg Lead Score', className: 'text-center', cell: (row) => <span className="font-semibold">{row.avg_lead_score}</span> },
    { id: 'cac', header: 'CAC ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">${row.cac}</span> },
    { id: 'roi_ratio', header: 'ROI Ratio', className: 'text-center', cell: (row) => <span className="font-bold text-purple-600">{row.roi_ratio}x</span> }
  ];

  const leaderboardColumns: DataTableColumn<any>[] = [
    {
      id: 'rank',
      header: 'Rank',
      className: 'text-center',
      cell: (row) => (
        <span className="h-6 w-6 rounded-full bg-amber-100 text-amber-800 font-extrabold text-xs inline-flex items-center justify-center">
          #{row.rank}
        </span>
      )
    },
    { id: 'name', header: 'Sales Executive', cell: (row) => <span className="font-bold text-slate-900">{row.name}</span> },
    { id: 'role', header: 'Role', cell: (row) => <span className="text-slate-500">{row.role}</span> },
    { id: 'deals_closed', header: 'Deals Closed', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.deals_closed}</span> },
    { id: 'revenue', header: 'Revenue ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.revenue?.toLocaleString()}</span> },
    { id: 'quota_target', header: 'Quota ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">${row.quota_target?.toLocaleString()}</span> },
    { id: 'attainment_pct', header: 'Attainment (%)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.attainment_pct}%</span> },
    { id: 'calls_made', header: 'Calls', className: 'text-center', cell: (row) => <span className="font-semibold">{row.calls_made}</span> },
    { id: 'meetings_held', header: 'Meetings', className: 'text-center', cell: (row) => <span className="font-semibold">{row.meetings_held}</span> },
    {
      id: 'badge',
      header: 'Status',
      className: 'text-center',
      cell: (row) => (
        <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${row.badge === 'Top Performer' ? 'bg-amber-100 text-amber-800' : (row.badge === 'Quota Met' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700')}`}>
          {row.badge}
        </span>
      )
    }
  ];

  const forecastColumns: DataTableColumn<any>[] = [
    { id: 'period', header: 'Forecast Period', cell: (row) => <span className="font-bold text-slate-900">{row.period}</span> },
    { id: 'committed_revenue', header: 'Committed ($)', className: 'text-right', cell: (row) => <span className="font-semibold text-slate-700">${row.committed_revenue?.toLocaleString()}</span> },
    { id: 'best_case_forecast', header: 'Best Case ($)', className: 'text-right', cell: (row) => <span className="font-semibold text-indigo-600">${row.best_case_forecast?.toLocaleString()}</span> },
    { id: 'pipeline_weighted', header: 'Weighted Pipeline ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.pipeline_weighted?.toLocaleString()}</span> },
    { id: 'target', header: 'Target Benchmark ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-500">${row.target?.toLocaleString()}</span> },
    { id: 'confidence_score', header: 'AI Confidence (%)', className: 'text-center', cell: (row) => <span className="font-bold text-purple-600">{row.confidence_score}%</span> },
    {
      id: 'forecast_status',
      header: 'Status',
      className: 'text-center',
      cell: (row) => (
        <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-indigo-100 text-indigo-800">
          {row.forecast_status}
        </span>
      )
    }
  ];

  const activityColumns: DataTableColumn<any>[] = [
    { id: 'rep_name', header: 'Sales Executive', cell: (row) => <span className="font-bold text-slate-900">{row.rep_name}</span> },
    { id: 'total_calls', header: 'Calls Made', className: 'text-center', cell: (row) => <span className="font-bold text-slate-800">{row.total_calls}</span> },
    { id: 'call_duration_mins', header: 'Duration (Mins)', className: 'text-center', cell: (row) => <span className="font-mono">{row.call_duration_mins} mins</span> },
    { id: 'emails_sent', header: 'Emails Sent', className: 'text-center', cell: (row) => <span className="font-bold text-slate-800">{row.emails_sent}</span> },
    { id: 'email_open_rate', header: 'Open Rate (%)', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.email_open_rate}%</span> },
    { id: 'meetings_conducted', header: 'Meetings', className: 'text-center', cell: (row) => <span className="font-bold text-purple-600">{row.meetings_conducted}</span> },
    { id: 'demos_given', header: 'Demos Given', className: 'text-center', cell: (row) => <span className="font-bold text-indigo-600">{row.demos_given}</span> },
    { id: 'activity_score', header: 'Activity Score', className: 'text-center', cell: (row) => <span className="font-extrabold text-blue-600">{row.activity_score}</span> }
  ];

  const durationColumns: DataTableColumn<any>[] = [
    { id: 'deal_tier', header: 'Deal Tier / Segment', cell: (row) => <span className="font-bold text-slate-900">{row.deal_tier}</span> },
    { id: 'deal_count', header: 'Deal Count', className: 'text-center', cell: (row) => <span className="font-semibold">{row.deal_count}</span> },
    { id: 'avg_cycle_days', header: 'Avg Cycle (Days)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.avg_cycle_days} Days</span> },
    { id: 'fastest_close_days', header: 'Fastest Close', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.fastest_close_days} Days</span> },
    { id: 'longest_close_days', header: 'Longest Close', className: 'text-center', cell: (row) => <span className="font-bold text-amber-600">{row.longest_close_days} Days</span> },
    { id: 'primary_bottleneck', header: 'Primary Lag Bottleneck', cell: (row) => <span className="text-slate-600">{row.primary_bottleneck}</span> }
  ];

  const unitEconomicsColumns: DataTableColumn<any>[] = [
    { id: 'segment', header: 'Customer Segment', cell: (row) => <span className="font-bold text-slate-900">{row.segment}</span> },
    { id: 'customer_count', header: 'Customers', className: 'text-center', cell: (row) => <span className="font-semibold">{row.customer_count}</span> },
    { id: 'avg_ltv', header: 'Avg LTV ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.avg_ltv?.toLocaleString()}</span> },
    { id: 'blended_cac', header: 'Blended CAC ($)', className: 'text-right', cell: (row) => <span className="font-mono font-bold text-slate-800">${row.blended_cac?.toLocaleString()}</span> },
    { id: 'paid_cac', header: 'Paid CAC ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">${row.paid_cac?.toLocaleString()}</span> },
    { id: 'organic_cac', header: 'Organic CAC ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">${row.organic_cac?.toLocaleString()}</span> },
    { id: 'ltv_cac_ratio', header: 'LTV : CAC Ratio', className: 'text-center', cell: (row) => <span className="font-extrabold text-purple-600">{row.ltv_cac_ratio}x</span> },
    { id: 'annual_churn_rate', header: 'Annual Churn (%)', className: 'text-center', cell: (row) => <span className="font-bold text-rose-600">{row.annual_churn_rate ?? row.churn_rate}%</span> }
  ];

  const quotaColumns: DataTableColumn<any>[] = [
    { id: 'rep_name', header: 'Sales Executive', cell: (row) => <span className="font-bold text-slate-900">{row.rep_name}</span> },
    { id: 'role', header: 'Role', cell: (row) => <span className="text-slate-500">{row.role}</span> },
    { id: 'assigned_quota', header: 'Assigned Quota ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">${row.assigned_quota?.toLocaleString()}</span> },
    { id: 'closed_revenue', header: 'Closed Revenue ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.closed_revenue?.toLocaleString()}</span> },
    { id: 'pipeline_coverage', header: 'Pipeline Coverage ($)', className: 'text-right', cell: (row) => <span className="font-mono font-semibold text-indigo-600">${row.pipeline_coverage?.toLocaleString()}</span> },
    {
      id: 'attainment_pct',
      header: 'Attainment Progress',
      className: 'text-center',
      cell: (row) => (
        <div className="flex items-center gap-2 justify-center">
          <div className="w-20 bg-slate-200 h-2 rounded-full overflow-hidden">
            <div className={`h-full ${row.attainment_pct >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${Math.min(100, row.attainment_pct)}%` }} />
          </div>
          <span className="font-bold text-[11px]">{row.attainment_pct}%</span>
        </div>
      )
    },
    {
      id: 'status',
      header: 'Status',
      className: 'text-center',
      cell: (row) => (
        <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${row.status === 'Target Met' ? 'bg-emerald-100 text-emerald-800' : (row.status === 'On Track' ? 'bg-indigo-100 text-indigo-800' : 'bg-rose-100 text-rose-800')}`}>
          {row.status}
        </span>
      )
    }
  ];

  const customColumns: DataTableColumn<any>[] = [
    { id: 'name', header: 'Report Query Name', cell: (row) => <span className="font-bold text-slate-900">{row.name}</span> },
    { id: 'filters', header: 'Applied Filter Query', cell: (row) => <span className="text-slate-600 font-mono">{row.filters || 'Enterprise Accounts'}</span> },
    { id: 'metrics_included', header: 'Metrics Included', cell: (row) => <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded text-[11px]">{Array.isArray(row.metrics_included) ? row.metrics_included.join(', ') : 'sales-performance'}</span> },
    { id: 'created_at', header: 'Created Date', cell: (row) => <span className="font-mono text-slate-500">{row.created_at}</span> },
    {
      id: 'actions',
      header: 'Action',
      className: 'text-center',
      cell: (row) => (
        <button onClick={() => setReportToDelete(row.id)} className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg cursor-pointer transition-colors">
          <Trash2 className="w-4 h-4" />
        </button>
      )
    }
  ];

  const scheduledColumns: DataTableColumn<any>[] = [
    { id: 'report_type', header: 'Report Target', cell: (row) => <span className="font-bold text-slate-900 uppercase">{row.report_type}</span> },
    { id: 'email', header: 'Recipient Email', cell: (row) => <span className="text-slate-700 font-mono">{row.email}</span> },
    { id: 'frequency', header: 'Delivery Frequency', className: 'text-center', cell: (row) => <span className="font-semibold text-purple-700">{row.frequency}</span> },
    { id: 'next_run', header: 'Next Scheduled Run', className: 'text-center', cell: (row) => <span className="font-mono text-slate-600">{row.next_run}</span> },
    {
      id: 'status',
      header: 'Job Status',
      className: 'text-center',
      cell: () => (
        <span className="px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full text-[11px] font-bold">
          Active Cron
        </span>
      )
    }
  ];

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-xs">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center justify-between p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl shadow-xs">
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
            Executive Reports & Analytics Center
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">High-density data tables, sales performance, pipeline velocity & AI revenue forecasting</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleExportCsv}
            disabled={exportCsvMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg font-semibold text-xs transition-colors shadow-xs cursor-pointer disabled:opacity-50"
          >
            {exportCsvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
            Export S3 CSV
          </button>

          <button
            onClick={handleExportPdf}
            disabled={exportPdfMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg font-semibold text-xs transition-colors shadow-xs cursor-pointer disabled:opacity-50"
          >
            {exportPdfMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4 text-indigo-600" />}
            Export PDF
          </button>

          <button
            onClick={() => setIsScheduleModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg font-semibold text-xs transition-colors shadow-xs cursor-pointer"
          >
            <Mail className="w-4 h-4 text-purple-600" />
            Schedule Delivery
          </button>

          <button
            onClick={() => setIsCustomModalOpen(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-xs cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            New Query Builder
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
          { id: 'unit-economics', label: 'Unit Economics', icon: Percent },
          { id: 'quota', label: 'Quota Attainment', icon: Layers },
          { id: 'custom', label: 'Custom Reports', icon: Filter },
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

      {/* Main DataTable Display Container */}
      <div className="space-y-6">

        {/* 1. SALES PERFORMANCE */}
        {activeCategory === 'performance' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 bg-emerald-50/70 border border-emerald-100 rounded-xl">
                <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">Total Team Revenue</span>
                <h4 className="text-2xl font-extrabold text-emerald-950 mt-1">
                  ${salesData?.metrics?.total_revenue !== undefined ? salesData.metrics.total_revenue.toLocaleString() : '0'}
                </h4>
              </div>
              <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-xl">
                <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider block">Monthly Target</span>
                <h4 className="text-2xl font-extrabold text-indigo-950 mt-1">
                  ${salesData?.metrics?.monthly_target !== undefined ? salesData.metrics.monthly_target.toLocaleString() : '250,000'}
                </h4>
              </div>
              <div className="p-4 bg-purple-50/70 border border-purple-100 rounded-xl">
                <span className="text-xs font-semibold text-purple-800 uppercase tracking-wider block">Overall Target Attainment</span>
                <h4 className="text-2xl font-extrabold text-purple-950 mt-1">
                  {salesData?.metrics?.total_revenue && salesData?.metrics?.monthly_target
                    ? ((salesData.metrics.total_revenue / salesData.metrics.monthly_target) * 100).toFixed(1)
                    : '0.0'}%
                </h4>
              </div>
            </div>

            <DataTable
              columns={performanceColumns}
              data={filterRows(salesData?.metrics?.table_rows || [], ['rep_name', 'role'])}
              getRowKey={(item) => item.rep_name}
              isLoading={isSalesLoading}
              emptyTitle="No Performance Data"
              emptyDescription="No sales rep records found for this period."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search sales executives..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 2. PIPELINE VELOCITY */}
        {activeCategory === 'velocity' && (
          <div className="space-y-6">
            <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-xl max-w-sm">
              <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider block">Average Total Sales Cycle</span>
              <h4 className="text-2xl font-extrabold text-indigo-950 mt-1">
                {velocityData?.metrics?.avg_days_to_close || 0} Days
              </h4>
            </div>

            <DataTable
              columns={velocityColumns}
              data={filterRows(velocityData?.metrics?.table_rows || [], ['stage', 'bottleneck_risk'])}
              getRowKey={(item) => item.stage}
              isLoading={isVelocityLoading}
              emptyTitle="No Pipeline Stage Data"
              emptyDescription="No deal stages found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search stage name..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 3. WIN/LOSS RATIO */}
        {activeCategory === 'winloss' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 bg-emerald-50/70 border border-emerald-100 rounded-xl">
                <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">Win Percentage</span>
                <h4 className="text-2xl font-extrabold text-emerald-950 mt-1">{winLossData?.metrics?.win_percentage ?? 0}%</h4>
              </div>
              <div className="p-4 bg-rose-50/70 border border-rose-100 rounded-xl">
                <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider block">Loss Percentage</span>
                <h4 className="text-2xl font-extrabold text-rose-950 mt-1">{winLossData?.metrics?.loss_percentage ?? 0}%</h4>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider block">Total Won Deals</span>
                <h4 className="text-2xl font-extrabold text-slate-900 mt-1">{winLossData?.metrics?.total_won_deals ?? 0}</h4>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider block">Total Lost Deals</span>
                <h4 className="text-2xl font-extrabold text-slate-900 mt-1">{winLossData?.metrics?.total_lost_deals ?? 0}</h4>
              </div>
            </div>

            <DataTable
              columns={winLossColumns}
              data={filterRows(winLossData?.metrics?.table_rows || [], ['segment', 'primary_loss_reason'])}
              getRowKey={(item) => item.segment}
              isLoading={isWinLossLoading}
              emptyTitle="No Win/Loss Data"
              emptyDescription="No segment data found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search market segment or loss reason..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 4. LEAD ATTRIBUTION */}
        {activeCategory === 'attribution' && (
          <div className="space-y-6">
            <DataTable
              columns={leadAttrColumns}
              data={filterRows(leadAttrData?.metrics?.table_rows || [], ['source'])}
              getRowKey={(item) => item.source}
              isLoading={isLeadAttrLoading}
              emptyTitle="No Lead Attribution Data"
              emptyDescription="No lead source data found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search lead channel..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 5. REP LEADERBOARD */}
        {activeCategory === 'leaderboard' && (
          <div className="space-y-6">
            <DataTable
              columns={leaderboardColumns}
              data={filterRows(leaderboardData?.metrics?.table_rows || [], ['name', 'role', 'badge'])}
              getRowKey={(item) => item.name}
              isLoading={isLeaderboardLoading}
              emptyTitle="No Leaderboard Data"
              emptyDescription="No sales executive rankings found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search sales executive name..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 6. REVENUE FORECASTING */}
        {activeCategory === 'forecasting' && (
          <div className="space-y-6">
            <DataTable
              columns={forecastColumns}
              data={filterRows(forecastData?.metrics?.table_rows || [], ['period', 'forecast_status'])}
              getRowKey={(item) => item.period}
              isLoading={isForecastLoading}
              emptyTitle="No Forecast Data"
              emptyDescription="No forecast periods found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search forecast period..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 7. ACTIVITY METRICS */}
        {activeCategory === 'activity' && (
          <div className="space-y-6">
            <DataTable
              columns={activityColumns}
              data={filterRows(activityData?.metrics?.table_rows || [], ['rep_name'])}
              getRowKey={(item) => item.rep_name}
              isLoading={isActivityLoading}
              emptyTitle="No Activity Data"
              emptyDescription="No rep activity records found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search rep name..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 8. DEAL DURATION */}
        {activeCategory === 'duration' && (
          <div className="space-y-6">
            <DataTable
              columns={durationColumns}
              data={filterRows(durationData?.metrics?.table_rows || [], ['deal_tier', 'primary_bottleneck'])}
              getRowKey={(item) => item.deal_tier}
              isLoading={isDurationLoading}
              emptyTitle="No Duration Data"
              emptyDescription="No deal tier records found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search deal tier..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 9. UNIT ECONOMICS */}
        {activeCategory === 'unit-economics' && (
          <div className="space-y-6">
            <DataTable
              columns={unitEconomicsColumns}
              data={filterRows(cacData?.metrics?.table_rows || [], ['segment'])}
              getRowKey={(item) => item.segment}
              isLoading={isCacLoading}
              emptyTitle="No Unit Economics Data"
              emptyDescription="No customer segment records found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search customer segment..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 10. QUOTA ATTAINMENT */}
        {activeCategory === 'quota' && (
          <div className="space-y-6">
            <DataTable
              columns={quotaColumns}
              data={filterRows(quotaData?.metrics?.table_rows || [], ['rep_name', 'role', 'status'])}
              getRowKey={(item) => item.rep_name}
              isLoading={isQuotaLoading}
              emptyTitle="No Quota Data"
              emptyDescription="No quota attainment records found."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search rep name..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 11. CUSTOM REPORTS */}
        {activeCategory === 'custom' && (
          <div className="space-y-6">
            <DataTable
              columns={customColumns}
              data={filterRows(customReports, ['name', 'filters'])}
              getRowKey={(item) => item.id}
              isLoading={isCustomLoading}
              emptyTitle="No Custom Reports"
              emptyDescription="No saved custom queries found. Click New Query Builder above to add one."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search custom report name..."
              pagination={{ pageSize: 10 }}
            />
          </div>
        )}

        {/* 12. SCHEDULED JOBS */}
        {activeCategory === 'scheduled' && (
          <div className="space-y-6">
            <DataTable
              columns={scheduledColumns}
              data={filterRows(scheduledReports, ['report_type', 'email', 'frequency'])}
              getRowKey={(item) => item.id}
              isLoading={isScheduledLoading}
              emptyTitle="No Scheduled Jobs"
              emptyDescription="No active scheduled report deliveries found. Click Schedule Delivery to add one."
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search scheduled email..."
              pagination={{ pageSize: 10 }}
            />
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
