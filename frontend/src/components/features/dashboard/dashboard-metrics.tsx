import type { ElementType } from 'react';
import {
  BadgeDollarSign,
  BriefcaseBusiness,
  CheckCircle2,
  FileText,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
  WalletCards,
} from 'lucide-react';

import { Card, Skeleton } from '@/components/ui';
import type { DashboardKPIs } from '@/lib/api/dashboard';
import { cn } from '@/lib/utils';

import { DashboardSectionError } from './dashboard-section-state';

type Comparison = {
  previous_value: number;
  change_percentage: number | null;
};

interface Metric {
  title: string;
  value: string;
  detail: string;
  icon: ElementType;
  iconClassName: string;
  comparison?: Comparison;
}

function Trend({ comparison }: { comparison?: Comparison }) {
  if (!comparison) {
    return <span className="text-[11px] text-slate-500">Current snapshot</span>;
  }

  if (comparison.change_percentage === null) {
    return <span className="text-[11px] text-slate-500">No previous baseline</span>;
  }

  const positive = comparison.change_percentage >= 0;
  const Icon = positive ? TrendingUp : TrendingDown;
  const direction = positive ? 'Increased' : 'Decreased';

  return (
    <span
      className={cn(
        'inline-flex min-w-0 items-center gap-1 text-[11px] font-semibold',
        positive ? 'text-emerald-600' : 'text-rose-600',
      )}
      aria-label={`${direction} ${Math.abs(comparison.change_percentage)}% vs previous period`}
    >
      <Icon className="size-3" aria-hidden="true" />
      <span>{Math.abs(comparison.change_percentage)}%</span>
      <span className="truncate font-normal text-slate-500">
        Previous: {comparison.previous_value.toLocaleString()}
      </span>
    </span>
  );
}

function MetricCell({ metric, index }: { metric: Metric; index: number }) {
  const Icon = metric.icon;

  return (
    <article
      className={cn(
        'min-w-0 border-slate-200 px-4 py-4 sm:px-5',
        index < 7 && 'border-b',
        index % 2 === 0 && 'md:border-r',
        index >= 6 && 'md:border-b-0',
        index % 2 === 1 && 'xl:border-r',
        index === 3 && 'xl:border-r-0',
        index === 7 && 'xl:border-r-0',
        index === 4 && 'xl:border-b-0',
        index === 5 && 'xl:border-b-0',
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn('size-4 shrink-0', metric.iconClassName)} aria-hidden="true" />
        <h2 className="truncate text-xs font-medium text-slate-700">{metric.title}</h2>
      </div>
      <div className="mt-2 flex min-w-0 items-end gap-2">
        <p className="truncate text-[1.35rem] font-semibold leading-none tracking-tight text-slate-950 tabular-nums">
          {metric.value}
        </p>
        <Trend comparison={metric.comparison} />
      </div>
      <p className="mt-2 truncate text-[10px] leading-4 text-slate-500">{metric.detail}</p>
    </article>
  );
}

export function DashboardKpiGrid({
  data,
  isLoading,
  isError,
  onRetry,
  formatCurrency,
}: {
  data?: DashboardKPIs;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  formatCurrency: (value: number) => string;
}) {
  if (isLoading) {
    return (
      <Card className="grid overflow-hidden shadow-none md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <Skeleton key={index} className="m-4 h-20 rounded-lg" />
        ))}
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card className="shadow-none">
        <DashboardSectionError message="Dashboard metrics could not be loaded." onRetry={onRetry} />
      </Card>
    );
  }

  const comparisons = data.comparisons ?? undefined;
  const metrics: Metric[] = [
    {
      title: 'New leads',
      value: data.total_leads.toLocaleString(),
      detail: 'Created in selected period',
      icon: Users,
      iconClassName: 'text-blue-600',
      comparison: comparisons?.total_leads,
    },
    {
      title: 'Open pipeline',
      value: formatCurrency(data.pipeline_revenue),
      detail: 'Current open opportunity value',
      icon: BriefcaseBusiness,
      iconClassName: 'text-cyan-600',
    },
    {
      title: 'Won revenue',
      value: formatCurrency(data.deals_won_amount),
      detail: 'Closed-won opportunity value',
      icon: BadgeDollarSign,
      iconClassName: 'text-amber-600',
      comparison: comparisons?.deals_won_amount,
    },
    {
      title: 'Win rate',
      value: data.closed_deals_count ? `${data.win_rate_percentage}%` : '—',
      detail: `${data.won_deals_count} of ${data.closed_deals_count} closed deals`,
      icon: Target,
      iconClassName: 'text-violet-600',
      comparison: comparisons?.win_rate_percentage,
    },
    {
      title: 'Deals won',
      value: data.won_deals_count.toLocaleString(),
      detail: 'Closed won in selected period',
      icon: CheckCircle2,
      iconClassName: 'text-emerald-600',
      comparison: comparisons?.won_deals_count,
    },
    {
      title: 'Quote value',
      value: formatCurrency(data.quote_value),
      detail: `${data.quote_count} quotes issued`,
      icon: FileText,
      iconClassName: 'text-indigo-600',
      comparison: comparisons?.quote_value,
    },
    {
      title: 'Collected payments',
      value: formatCurrency(data.revenue),
      detail: `${data.collection_rate_percentage}% collection rate`,
      icon: WalletCards,
      iconClassName: 'text-teal-600',
      comparison: comparisons?.revenue,
    },
    {
      title: 'Outstanding invoices',
      value: formatCurrency(data.outstanding_amount),
      detail: `${data.pending_payment_count} payments pending`,
      icon: TrendingUp,
      iconClassName: 'text-rose-500',
    },
  ];

  return (
    <Card
      className="grid overflow-hidden shadow-none md:grid-cols-2 xl:grid-cols-4"
      aria-label="Dashboard metrics"
    >
      {metrics.map((metric, index) => (
        <MetricCell key={metric.title} metric={metric} index={index} />
      ))}
    </Card>
  );
}
