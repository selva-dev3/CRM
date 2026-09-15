'use client';

import Link from 'next/link';
import { BarChart3, LineChart as LineChartIcon, MoreVertical } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui';
import type { FunnelStageItem, LeadConversionItem, RevenueChart } from '@/lib/api/dashboard';

import {
  DashboardSectionEmpty,
  DashboardSectionError,
  DashboardSectionSkeleton,
} from './dashboard-section-state';

function ChartHeader({
  icon: Icon,
  title,
  description,
  href,
  linkLabel,
}: {
  icon: typeof BarChart3;
  title: string;
  description: string;
  href: string;
  linkLabel: string;
}) {
  return (
    <CardHeader className="flex-row items-start justify-between gap-3 border-b border-slate-100 px-4 py-3.5">
      <div className="min-w-0">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <Icon className="size-4 text-blue-600" aria-hidden="true" />
          {title}
        </CardTitle>
        <p className="mt-1 truncate text-[11px] text-slate-500">{description}</p>
      </div>
      <Button asChild variant="ghost" size="icon-sm" className="-mr-2 -mt-1 shrink-0 text-slate-500">
        <Link href={href} aria-label={linkLabel} title={linkLabel}>
          <MoreVertical className="size-4" />
        </Link>
      </Button>
    </CardHeader>
  );
}

export function RevenueTrendCard({
  data,
  isLoading,
  isError,
  onRetry,
  formatCurrency,
}: {
  data?: RevenueChart;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  formatCurrency: (value: number) => string;
}) {
  const chartData = data?.months.map((month, index) => ({
    month,
    revenue: data.actual[index] ?? 0,
  })) ?? [];
  const total = chartData.reduce((sum, item) => sum + item.revenue, 0);

  return (
    <Card className="flex min-h-[350px] min-w-0 flex-col shadow-none">
      <ChartHeader
        icon={LineChartIcon}
        title="Won revenue"
        description="Closed-won value over the selected period"
        href="/deals"
        linkLabel="View won deals"
      />
      <CardContent className="flex flex-1 flex-col p-4">
        {isLoading && <DashboardSectionSkeleton className="h-64" />}
        {isError && (
          <DashboardSectionError message="Revenue trend could not be loaded." onRetry={onRetry} />
        )}
        {!isLoading && !isError && chartData.length === 0 && (
          <DashboardSectionEmpty
            title="No won revenue yet"
            description="Closed-won opportunities in this period will appear here."
          />
        )}
        {!isLoading && !isError && chartData.length > 0 && (
          <>
            <div className="mb-3 flex items-center justify-between rounded-md border border-slate-200 bg-slate-50/70 px-3 py-2">
              <span className="text-[11px] font-medium text-slate-600">Won deal total</span>
              <span className="text-xs font-semibold text-slate-950 tabular-nums">
                {formatCurrency(total)}
              </span>
            </div>
            <div className="min-h-0 flex-1" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%" minHeight={220}>
                <LineChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="2 2" />
                  <XAxis
                    dataKey="month"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#64748b', fontSize: 10 }}
                    minTickGap={24}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    width={54}
                    tick={{ fill: '#64748b', fontSize: 10 }}
                    tickFormatter={(value) =>
                      new Intl.NumberFormat(undefined, { notation: 'compact' }).format(Number(value))
                    }
                  />
                  <Tooltip
                    formatter={(value) => [formatCurrency(Number(value)), 'Won revenue']}
                    contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 11 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="revenue"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: '#fff', strokeWidth: 1.5 }}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <table className="sr-only">
              <caption>Won revenue by month</caption>
              <thead><tr><th>Month</th><th>Revenue</th></tr></thead>
              <tbody>
                {chartData.map((item) => (
                  <tr key={item.month}><td>{item.month}</td><td>{formatCurrency(item.revenue)}</td></tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function PipelineCard({
  data,
  isLoading,
  isError,
  onRetry,
  formatCurrency,
}: {
  data: FunnelStageItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  formatCurrency: (value: number) => string;
}) {
  const stages = data.filter((stage) => !stage.stage.toLowerCase().includes('lost')).slice(0, 5);
  const maximum = Math.max(...stages.map((stage) => stage.count), 0);
  const hasData = stages.some((stage) => stage.count > 0);

  return (
    <Card className="flex min-h-[350px] min-w-0 flex-col shadow-none">
      <ChartHeader
        icon={BarChart3}
        title="Sales pipeline funnel"
        description="Opportunity progression by stage"
        href="/pipelines"
        linkLabel="Open pipeline"
      />
      <CardContent className="flex flex-1 flex-col p-4">
        {isLoading && <DashboardSectionSkeleton className="h-64" />}
        {isError && (
          <DashboardSectionError message="Sales pipeline could not be loaded." onRetry={onRetry} />
        )}
        {!isLoading && !isError && !hasData && (
          <DashboardSectionEmpty
            title="No active pipeline"
            description="Create an opportunity to start tracking pipeline movement."
          />
        )}
        {!isLoading && !isError && hasData && (
          <div className="flex flex-1 items-end gap-2 pt-2 sm:gap-3" role="list" aria-label="Pipeline stages">
            {stages.map((stage) => {
              const percentage = maximum > 0 ? Math.round((stage.count / maximum) * 100) : 0;
              const height = stage.count > 0 ? Math.max(percentage, 8) : 0;
              return (
                <div key={stage.stage} className="flex h-full min-w-0 flex-1 flex-col justify-end" role="listitem">
                  <div className="mb-2 text-center">
                    <p className="text-sm font-semibold text-slate-950 tabular-nums">{percentage}%</p>
                    <p className="text-[10px] text-slate-500">{stage.count} deals</p>
                  </div>
                  <div className="flex h-44 items-end overflow-hidden rounded-md bg-blue-50">
                    <div
                      className="w-full rounded-md bg-blue-300 transition-[height] duration-300"
                      style={{ height: `${height}%` }}
                      role="progressbar"
                      aria-label={`${stage.stage}: ${stage.count} deals, ${formatCurrency(stage.value)}`}
                      aria-valuemin={0}
                      aria-valuemax={maximum}
                      aria-valuenow={stage.count}
                    />
                  </div>
                  <p className="mt-2 truncate text-center text-[10px] font-medium text-slate-600" title={stage.stage}>
                    {stage.stage}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function LeadConversionCard({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data: LeadConversionItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <Card className="shadow-none">
      <ChartHeader
        icon={BarChart3}
        title="Lead channels"
        description="Volume and conversion by acquisition source"
        href="/leads"
        linkLabel="View leads"
      />
      <CardContent className="p-4">
        {isLoading && <DashboardSectionSkeleton className="h-40" />}
        {isError && (
          <DashboardSectionError message="Lead channel data could not be loaded." onRetry={onRetry} />
        )}
        {!isLoading && !isError && data.length === 0 && (
          <DashboardSectionEmpty
            title="No lead-source data"
            description="Lead acquisition channels will appear as leads are created."
          />
        )}
        {!isLoading && !isError && data.length > 0 && (
          <div className="space-y-3">
            {data.slice(0, 5).map((item) => (
              <div key={item.source} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                <div className="min-w-0">
                  <div className="flex justify-between gap-3 text-xs">
                    <span className="truncate font-semibold text-slate-700">{item.source}</span>
                    <span className="text-slate-500">{item.leads} leads</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-emerald-500" style={{ width: `${item.rate}%` }} />
                  </div>
                </div>
                <span className="w-12 text-right text-xs font-semibold text-slate-900 tabular-nums">
                  {item.rate}%
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
