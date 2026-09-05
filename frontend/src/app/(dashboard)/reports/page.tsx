'use client';

import { Input } from "@/components/ui/input";

import { getErrorMessage } from '@/lib/utils';
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
import { ActionMenu } from '@/components/common/action-menu';
import { DataTable, DataTableColumn } from '@/components/common/data-table';
import { Button } from '@/components/ui/button';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { CustomSelect } from '@/components/common/custom-select';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
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
  useQuotaAttainmentReportQuery,
  useCustomReportsQuery,
  useScheduledReportsQuery,
  useCreateCustomReportMutation,
  useDeleteCustomReportMutation,
  useExportReportPdfMutation,
  useExportReportCsvMutation,
  useScheduleReportEmailMutation
} from '@/lib/api/reports';
import type { CustomReportItem, ReportRow, ScheduledReportItem } from '@/lib/api/reports';

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
  const { data: activityData } = useActivityMetricsReportQuery();
  const { data: durationData, isLoading: isDurationLoading } = useDealDurationReportQuery();
  const { data: cacData, isLoading: isCacLoading } = useCacReportQuery();
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to export PDF.'));
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportCsvMutation.mutateAsync(activeCategory);
      setSuccessMessage(`CSV dataset uploaded to S3 bucket. Download started.`);
      window.open(res.csv_url, '_blank');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to export CSV dataset.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create custom report.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to schedule email delivery.'));
    }
  };

  const handleDeleteCustomReport = async () => {
    if (!reportToDelete) return;
    try {
      await deleteCustomMutation.mutateAsync(reportToDelete);
      setSuccessMessage('Custom report query deleted.');
      setReportToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete custom report.'));
    }
  };

  // Helper search filter
  const filterRows = <T extends object>(rows: T[], keys: string[]): T[] => {
    if (!searchQuery.trim()) return rows;
    const query = searchQuery.toLowerCase().trim();
    return rows.filter((r) => {
      const record = r as Record<string, unknown>;
      return keys.some((k) => String(record[k] ?? '').toLowerCase().includes(query));
    });
  };

  // Column Definitions
  const performanceColumns: DataTableColumn<ReportRow>[] = [
    { id: 'rep_name', header: 'Sales Executive', cell: (row) => <span className="font-bold text-slate-900">{row.rep_name}</span> },
    { id: 'role', header: 'Role', cell: (row) => <span className="text-slate-500">{row.role}</span> },
    { id: 'deals_assigned', header: 'Assigned', className: 'text-center', cell: (row) => <span className="font-semibold">{row.deals_assigned}</span> },
    { id: 'deals_closed', header: 'Closed', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-700">{row.deals_closed}</span> },
    { id: 'win_rate', header: 'Win Rate (%)', className: 'text-center', cell: (row) => <span className="font-bold">{row.win_rate}%</span> },
    { id: 'revenue', header: 'Revenue ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.revenue?.toLocaleString()}</span> },
    { id: 'quota_target', header: 'Quota ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">{row.quota_target != null ? `$${row.quota_target.toLocaleString()}` : '—'}</span> },
    {
      id: 'attainment_pct',
      header: 'Attainment Progress',
      className: 'text-center',
      cell: (row) => (
        <div className="flex items-center gap-2 justify-center">
          {row.attainment_pct == null ? (
            <span className="text-slate-400 text-[11px]">No quota set</span>
          ) : (
            <>
              <div className="w-20 bg-slate-200 h-2 rounded-full overflow-hidden">
                <div className={`h-full ${row.attainment_pct >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${Math.min(100, row.attainment_pct)}%` }} />
              </div>
              <span className="font-bold text-[11px]">{row.attainment_pct}%</span>
            </>
          )}
        </div>
      )
    },
    { id: 'avg_deal_size', header: 'Avg Deal Size ($)', className: 'text-right', cell: (row) => <span className="font-mono">${row.avg_deal_size?.toLocaleString()}</span> }
  ];

  const velocityColumns: DataTableColumn<ReportRow>[] = [
    { id: 'stage', header: 'Pipeline Stage', cell: (row) => <span className="font-bold text-slate-900">{row.stage}</span> },
    { id: 'deal_count', header: 'Active Deals', className: 'text-center', cell: (row) => <span className="font-semibold">{row.deal_count}</span> },
    { id: 'total_value', header: 'Stage Value ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.total_value?.toLocaleString()}</span> },
    { id: 'avg_days_in_stage', header: 'Avg Days in Stage', className: 'text-center', cell: (row) => <span className="font-bold text-indigo-600">{row.avg_days_in_stage} Days</span> },
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

  const winLossColumns: DataTableColumn<ReportRow>[] = [
    { id: 'segment', header: 'Market Industry Segment', cell: (row) => <span className="font-bold text-slate-900">{row.segment}</span> },
    { id: 'won_deals', header: 'Won Deals', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.won_deals}</span> },
    { id: 'lost_deals', header: 'Lost Deals', className: 'text-center', cell: (row) => <span className="font-bold text-rose-600">{row.lost_deals}</span> },
    { id: 'total_deals', header: 'Total Deals', className: 'text-center', cell: (row) => <span className="font-semibold">{row.total_deals}</span> },
    { id: 'win_percentage', header: 'Win Rate (%)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.win_percentage}%</span> },
    { id: 'won_value', header: 'Won Revenue ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.won_value?.toLocaleString()}</span> },
    { id: 'lost_value', header: 'Lost Opportunity ($)', className: 'text-right', cell: (row) => <span className="font-mono text-rose-500">${row.lost_value?.toLocaleString()}</span> },
    { id: 'primary_loss_reason', header: 'Primary Loss Reason', cell: (row) => <span className="text-slate-600">{row.primary_loss_reason}</span> }
  ];

  const leadAttrColumns: DataTableColumn<ReportRow>[] = [
    { id: 'source', header: 'Lead Source Channel', cell: (row) => <span className="font-bold text-slate-900">{row.source}</span> },
    { id: 'total_leads', header: 'Total Leads', className: 'text-center', cell: (row) => <span className="font-semibold">{row.total_leads}</span> },
    { id: 'converted_leads', header: 'Converted Leads', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.converted_leads}</span> },
    { id: 'conversion_rate', header: 'Conversion Rate (%)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.conversion_rate}%</span> },
    { id: 'avg_lead_score', header: 'Avg Lead Score', className: 'text-center', cell: (row) => <span className="font-semibold">{row.avg_lead_score}</span> }
  ];

  const leaderboardColumns: DataTableColumn<ReportRow>[] = [
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
    { id: 'quota_target', header: 'Quota ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-600">{row.quota_target != null ? `$${row.quota_target.toLocaleString()}` : '—'}</span> },
    { id: 'attainment_pct', header: 'Attainment (%)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.attainment_pct != null ? `${row.attainment_pct}%` : '—'}</span> },
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

  const forecastColumns: DataTableColumn<ReportRow>[] = [
    { id: 'period', header: 'Forecast Period', cell: (row) => <span className="font-bold text-slate-900">{row.period}</span> },
    { id: 'open_deals', header: 'Open Deals', className: 'text-center', cell: (row) => <span className="font-semibold">{row.open_deals}</span> },
    { id: 'pipeline_amount', header: 'Pipeline ($)', className: 'text-right', cell: (row) => <span className="font-semibold text-indigo-600">${row.pipeline_amount?.toLocaleString()}</span> },
    { id: 'pipeline_weighted', header: 'Weighted Pipeline ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.pipeline_weighted?.toLocaleString()}</span> }
  ];

  const durationColumns: DataTableColumn<ReportRow>[] = [
    { id: 'deal_tier', header: 'Deal Tier / Segment', cell: (row) => <span className="font-bold text-slate-900">{row.deal_tier}</span> },
    { id: 'deal_count', header: 'Deal Count', className: 'text-center', cell: (row) => <span className="font-semibold">{row.deal_count}</span> },
    { id: 'avg_cycle_days', header: 'Avg Cycle (Days)', className: 'text-center', cell: (row) => <span className="font-extrabold text-indigo-600">{row.avg_cycle_days} Days</span> },
    { id: 'fastest_close_days', header: 'Fastest Close', className: 'text-center', cell: (row) => <span className="font-bold text-emerald-600">{row.fastest_close_days} Days</span> },
    { id: 'longest_close_days', header: 'Longest Close', className: 'text-center', cell: (row) => <span className="font-bold text-amber-600">{row.longest_close_days} Days</span> },
    { id: 'primary_bottleneck', header: 'Primary Lag Bottleneck', cell: (row) => <span className="text-slate-600">{row.primary_bottleneck}</span> }
  ];

  const unitEconomicsColumns: DataTableColumn<ReportRow>[] = [
    { id: 'segment', header: 'Customer Segment', cell: (row) => <span className="font-bold text-slate-900">{row.segment}</span> },
    { id: 'customer_count', header: 'Customers', className: 'text-center', cell: (row) => <span className="font-semibold">{row.customer_count}</span> },
    { id: 'avg_ltv', header: 'Avg LTV ($)', className: 'text-right', cell: (row) => <span className="font-extrabold text-emerald-600">${row.avg_ltv?.toLocaleString()}</span> },
    { id: 'total_revenue', header: 'Total Revenue ($)', className: 'text-right', cell: (row) => <span className="font-mono text-slate-700">${row.total_revenue?.toLocaleString()}</span> }
  ];

  const quotaColumns: DataTableColumn<ReportRow>[] = [
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
          {row.attainment_pct == null ? (
            <span className="text-slate-400 text-[11px]">No quota set</span>
          ) : (
            <>
              <div className="w-20 bg-slate-200 h-2 rounded-full overflow-hidden">
                <div className={`h-full ${row.attainment_pct >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${Math.min(100, row.attainment_pct)}%` }} />
              </div>
              <span className="font-bold text-[11px]">{row.attainment_pct}%</span>
            </>
          )}
        </div>
      )
    },
    {
      id: 'status',
      header: 'Status',
      className: 'text-center',
      cell: (row) => (
        <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${row.status === 'Target Met' ? 'bg-emerald-100 text-emerald-800' : (row.status === 'On Track' ? 'bg-indigo-100 text-indigo-800' : (row.status === 'No Quota Set' ? 'bg-slate-100 text-slate-500' : 'bg-rose-100 text-rose-800'))}`}>
          {row.status}
        </span>
      )
    }
  ];

  const customColumns: DataTableColumn<CustomReportItem>[] = [
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

  const scheduledColumns: DataTableColumn<ScheduledReportItem>[] = [
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
          <button type="button" aria-label="Dismiss success message" onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
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
          <button type="button" aria-label="Dismiss error message" onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 w-full">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2 sm:gap-2.5 break-words">
            <BarChart3 className="w-6 h-6 sm:w-7 sm:h-7 text-indigo-600 shrink-0" />
            <span>Executive Reports & Analytics Center</span>
          </h1>
          <p className="text-slate-500 text-xs sm:text-sm mt-0.5">
            High-density data tables, sales performance, pipeline velocity & AI revenue forecasting
          </p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <PermissionGate permission={PERMISSIONS.REPORTS.CREATE}>
            <Button
              onClick={() => setIsCustomModalOpen(true)}
              className="w-full gap-2 text-xs font-semibold sm:w-auto"
            >
              <Plus className="w-4 h-4" />
              <span>New Query Builder</span>
            </Button>
          </PermissionGate>

          <ActionMenu
            label="More"
            className="w-full text-xs font-semibold sm:w-auto"
            actions={[
              {
                label: 'Export S3 CSV',
                permission: PERMISSIONS.REPORTS.EXPORT,
                icon: exportCsvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4 text-emerald-600" />,
                disabled: exportCsvMutation.isPending,
                onSelect: handleExportCsv,
              },
              {
                label: 'Export PDF',
                permission: PERMISSIONS.REPORTS.EXPORT,
                icon: exportPdfMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4 text-indigo-600" />,
                disabled: exportPdfMutation.isPending,
                onSelect: handleExportPdf,
              },
              {
                label: 'Schedule delivery',
                permission: PERMISSIONS.REPORTS.SCHEDULE,
                icon: <Mail className="w-4 h-4 text-purple-600" />,
                onSelect: () => setIsScheduleModalOpen(true),
              },
            ]}
          />
        </div>
      </div>

      {/* Navigation Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-2 border-b border-slate-200 w-full">
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
              className={`flex items-center gap-2 px-3 sm:px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors cursor-pointer shrink-0 ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-white' : 'text-slate-500'}`} />
              <span>{tab.label}</span>
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
                  ${salesData?.metrics?.total_revenue != null ? salesData.metrics.total_revenue.toLocaleString() : '0'}
                </h4>
              </div>
              <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-xl">
                <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider block">Monthly Target</span>
                <h4 className="text-2xl font-extrabold text-indigo-950 mt-1">
                  ${salesData?.metrics?.monthly_target != null ? salesData.metrics.monthly_target.toLocaleString() : '—'}
                </h4>
              </div>
              <div className="p-4 bg-purple-50/70 border border-purple-100 rounded-xl">
                <span className="text-xs font-semibold text-purple-800 uppercase tracking-wider block">Overall Target Attainment</span>
                <h4 className="text-2xl font-extrabold text-purple-950 mt-1">
                  {salesData?.metrics?.total_revenue != null && salesData?.metrics?.monthly_target != null
                    ? ((salesData.metrics.total_revenue / salesData.metrics.monthly_target) * 100).toFixed(1)
                    : '0.0'}%
                </h4>
              </div>
            </div>

            <DataTable
              columns={performanceColumns}
              data={filterRows(salesData?.metrics?.table_rows || [], ['rep_name', 'role'])}
              getRowKey={(item) => item.rep_name ?? item.id}
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
              getRowKey={(item) => item.stage ?? item.id}
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
              getRowKey={(item) => item.segment ?? item.id}
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
              getRowKey={(item) => item.source ?? item.id}
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
              getRowKey={(item) => item.name ?? item.id}
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
              getRowKey={(item) => item.period ?? item.id}
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
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-50/70 border border-slate-100 rounded-xl">
                <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider block">Total Calls</span>
                <h4 className="text-2xl font-extrabold text-slate-900 mt-1">{activityData?.metrics?.total_calls ?? 0}</h4>
                <span className="text-xs text-slate-500">{activityData?.metrics?.total_call_duration_minutes ?? 0} mins total</span>
              </div>
              <div className="p-4 bg-emerald-50/70 border border-emerald-100 rounded-xl">
                <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">Emails Sent</span>
                <h4 className="text-2xl font-extrabold text-emerald-950 mt-1">{activityData?.metrics?.total_emails ?? 0}</h4>
                <span className="text-xs text-emerald-700">{activityData?.metrics?.email_open_rate_pct ?? 0}% open rate</span>
              </div>
              <div className="p-4 bg-purple-50/70 border border-purple-100 rounded-xl">
                <span className="text-xs font-semibold text-purple-800 uppercase tracking-wider block">Meetings Held</span>
                <h4 className="text-2xl font-extrabold text-purple-950 mt-1">{activityData?.metrics?.total_meetings ?? 0}</h4>
              </div>
            </div>
            <p className="text-sm text-slate-500">Per-rep activity breakdown is unavailable because calls, emails, and meetings are not attributed to individual users in the current data model.</p>
          </div>
        )}

        {/* 8. DEAL DURATION */}
        {activeCategory === 'duration' && (
          <div className="space-y-6">
            <DataTable
              columns={durationColumns}
              data={filterRows(durationData?.metrics?.table_rows || [], ['deal_tier', 'primary_bottleneck'])}
              getRowKey={(item) => item.deal_tier ?? item.id}
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
              getRowKey={(item) => item.segment ?? item.id}
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
              getRowKey={(item) => item.rep_name ?? item.id}
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
        <ModalShell
          isOpen={isCustomModalOpen}
          onClose={() => setIsCustomModalOpen(false)}
          size="md"
          title={
            <h3 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
              <Plus className="w-5 h-5 text-indigo-600 shrink-0" />
              <span>Custom Query Builder</span>
            </h3>
          }
        >
          <form onSubmit={handleCreateCustomSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Report Name *</label>
              <Input
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
              <Input
                type="text"
                value={customFilters}
                onChange={(e) => setCustomFilters(e.target.value)}
                placeholder="e.g. Enterprise Tier Only"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setIsCustomModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600 w-full sm:w-auto cursor-pointer">
                Cancel
              </button>
              <button
                type="submit"
                disabled={createCustomMutation.isPending}
                className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50 w-full sm:w-auto"
              >
                {createCustomMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />}
                <span>Save Custom Report</span>
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Schedule Automated Delivery Modal */}
      {isScheduleModalOpen && (
        <ModalShell
          isOpen={isScheduleModalOpen}
          onClose={() => setIsScheduleModalOpen(false)}
          size="md"
          title={
            <h3 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
              <Mail className="w-5 h-5 text-purple-600 shrink-0" />
              <span>Schedule Automated Email Report</span>
            </h3>
          }
        >
          <form onSubmit={handleScheduleEmailSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Target Report</label>
              <CustomSelect
                value={scheduleReportType}
                onChange={setScheduleReportType}
                color="purple"
                options={[
                  { value: 'sales-performance', label: 'Sales Performance' },
                  { value: 'pipeline-velocity', label: 'Pipeline Velocity' },
                  { value: 'win-loss-ratio', label: 'Win/Loss Ratio' },
                  { value: 'revenue-forecasting', label: 'Revenue Forecast' },
                ]}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Recipient Email Address *</label>
              <Input
                type="email"
                required
                value={scheduleEmail}
                onChange={(e) => setScheduleEmail(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Delivery Frequency</label>
              <CustomSelect
                value={scheduleFrequency}
                onChange={setScheduleFrequency}
                color="purple"
                options={[
                  { value: 'Daily', label: 'Daily' },
                  { value: 'Weekly', label: 'Weekly' },
                  { value: 'Monthly', label: 'Monthly' },
                ]}
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setIsScheduleModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600 w-full sm:w-auto cursor-pointer">
                Cancel
              </button>
              <button
                type="submit"
                disabled={scheduleEmailMutation.isPending}
                className="flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50 w-full sm:w-auto"
              >
                {scheduleEmailMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />}
                <span>Schedule Delivery</span>
              </button>
            </div>
          </form>
        </ModalShell>
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
