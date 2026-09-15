import type { ElementType } from 'react';
import { BadgeDollarSign, BriefcaseBusiness, CheckCircle2, FileText, Target, TrendingDown, TrendingUp, Users } from 'lucide-react';
import { Card, Skeleton } from '@/components/ui';
import type { DashboardKPIs } from '@/lib/api/dashboard';
import { cn } from '@/lib/utils';
import { DashboardSectionError } from './dashboard-section-state';

type Comparison = { previous_value: number; change_percentage: number | null };
function Trend({ comparison }: { comparison?: Comparison }) {
  if (!comparison) return <span className="text-xs text-slate-500">Current snapshot</span>;
  if (comparison.change_percentage === null) return <span className="text-xs font-medium text-slate-500">No prior-period baseline</span>;
  const positive = comparison.change_percentage >= 0; const Icon = positive ? TrendingUp : TrendingDown;
  return <span className={cn('inline-flex items-center gap-1 text-xs font-semibold', positive ? 'text-emerald-700' : 'text-rose-700')}><Icon className="size-3.5" aria-hidden="true" />{positive ? 'Increased' : 'Decreased'} {Math.abs(comparison.change_percentage)}% vs previous period</span>;
}
function KpiCard({ title, value, detail, icon: Icon, comparison, tone }: { title: string; value: string; detail: string; icon: ElementType; comparison?: Comparison; tone: string }) {
  return <Card className="min-w-0 p-4 shadow-none sm:p-5"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-xs font-semibold text-slate-500">{title}</p><p className="mt-2 truncate text-2xl font-bold tracking-tight text-slate-950 tabular-nums">{value}</p></div><span className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', tone)}><Icon className="size-4" aria-hidden="true" /></span></div><div className="mt-3 min-h-8"><Trend comparison={comparison} /><p className="mt-1 truncate text-[11px] text-slate-500">{detail}</p></div></Card>;
}
export function DashboardKpiGrid({ data, isLoading, isError, onRetry, formatCurrency }: { data?: DashboardKPIs; isLoading: boolean; isError: boolean; onRetry: () => void; formatCurrency: (value: number) => string }) {
  if (isLoading) return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-36 rounded-card" />)}</div>;
  if (isError || !data) return <Card><DashboardSectionError message="Executive metrics could not be loaded." onRetry={onRetry} /></Card>;
  const comparisons = data.comparisons ?? undefined;
  return <><section aria-label="Executive metrics" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><KpiCard title="New leads" value={data.total_leads.toLocaleString()} detail="Created in the selected period" icon={Users} comparison={comparisons?.total_leads} tone="bg-blue-50 text-blue-700" /><KpiCard title="Open pipeline" value={formatCurrency(data.pipeline_revenue)} detail="Current value of open opportunities" icon={BriefcaseBusiness} tone="bg-indigo-50 text-indigo-700" /><KpiCard title="Won revenue" value={formatCurrency(data.deals_won_amount)} detail={`${data.won_deals_count} closed-won opportunities`} icon={BadgeDollarSign} comparison={comparisons?.deals_won_amount} tone="bg-emerald-50 text-emerald-700" /><KpiCard title="Win rate" value={data.closed_deals_count ? `${data.win_rate_percentage}%` : '—'} detail={`${data.won_deals_count} of ${data.closed_deals_count} closed deals won`} icon={Target} comparison={comparisons?.win_rate_percentage} tone="bg-amber-50 text-amber-700" /></section><section aria-label="Financial summary" className="grid overflow-hidden rounded-card border border-slate-200 bg-white sm:grid-cols-2 xl:grid-cols-4">{[
    { label: 'Deals won', value: data.won_deals_count.toLocaleString(), icon: CheckCircle2 }, { label: 'Quote value', value: formatCurrency(data.quote_value), icon: FileText }, { label: 'Collected payments', value: formatCurrency(data.revenue), icon: BadgeDollarSign }, { label: 'Outstanding invoices', value: formatCurrency(data.outstanding_amount), icon: TrendingUp },
  ].map(({ label, value, icon: Icon }, index) => <div key={label} className={cn('flex items-center gap-3 border-slate-100 px-4 py-3.5', index > 0 && 'border-t sm:border-l sm:border-t-0', index === 2 && 'sm:border-l-0 sm:border-t xl:border-l xl:border-t-0')}><Icon className="size-4 text-slate-400" aria-hidden="true" /><div className="min-w-0"><p className="text-[11px] font-medium text-slate-500">{label}</p><p className="truncate text-sm font-bold text-slate-900 tabular-nums">{value}</p></div></div>)}</section></>;
}
