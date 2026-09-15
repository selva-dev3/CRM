'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, CalendarRange, RefreshCw, SlidersHorizontal } from 'lucide-react';

import { ModalShell } from '@/components/common/modal-shell';
import {
  Button,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from '@/components/ui';
import { useHasPermission } from '@/hooks/use-has-permission';
import { fetchActivitiesPageApi } from '@/lib/api/activities';
import { fetchContactsApi } from '@/lib/api/contacts';
import {
  DEFAULT_DASHBOARD_CURRENCY,
  DEFAULT_DASHBOARD_LOCALE,
  dashboardQueryKeys,
  useActivitiesSummaryQuery,
  useCustomWidgetsQuery,
  useDashboardAiInsightsQuery,
  useDashboardKpisQuery,
  useLeadConversionsQuery,
  useRecentDealsQuery,
  useRevenueChartQuery,
  useSalesFunnelQuery,
  useSaveCustomWidgetsMutation,
  useTopPerformersQuery,
  type CustomWidget,
} from '@/lib/api/dashboard';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

import { DashboardAiPanel } from './dashboard-ai-panel';
import { LeadConversionCard, PipelineCard, RevenueTrendCard } from './dashboard-analytics';
import { DashboardDealsTable } from './dashboard-deals-table';
import { DashboardKpiGrid } from './dashboard-metrics';
import { DASHBOARD_RANGES, getDashboardDateRange, isDashboardRange } from './dashboard-range';
import {
  ActivitySummaryCard,
  RecentActivityCard,
  RecentContactsCard,
  TopPerformersCard,
} from './dashboard-side-panels';

const DEFAULT_WIDGETS: CustomWidget[] = [
  { id: 'w-kpis', title: 'Executive KPIs', enabled: true },
  { id: 'w-revenue', title: 'Won Revenue Trend', enabled: true },
  { id: 'w-funnel', title: 'Sales Pipeline', enabled: true },
  { id: 'w-conversions', title: 'Lead Channels', enabled: true },
  { id: 'w-activity', title: 'Activity Summary', enabled: true },
  { id: 'w-contacts', title: 'Recent Contacts', enabled: true },
  { id: 'w-deals', title: 'Recent Deals', enabled: true },
  { id: 'w-top', title: 'Top Performers', enabled: true },
  { id: 'w-ai', title: 'AI Recommendations', enabled: true },
];

export function DashboardView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { hasPermission } = useHasPermission();
  const rangeParam = searchParams.get('range');
  const rangeKey = isDashboardRange(rangeParam) ? rangeParam : '30d';
  const [anchor] = useState(() => new Date());
  const range = useMemo(() => getDashboardDateRange(rangeKey, anchor), [anchor, rangeKey]);
  const [customizing, setCustomizing] = useState(false);
  const [draft, setDraft] = useState<CustomWidget[] | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [widgetError, setWidgetError] = useState<string | null>(null);

  const widgetsQuery = useCustomWidgetsQuery();
  const widgets = useMemo(() => {
    const saved = new Map((widgetsQuery.data ?? []).map((item) => [item.id, item.enabled]));
    return DEFAULT_WIDGETS.map((item) => ({
      ...item,
      enabled: saved.get(item.id) ?? item.enabled,
    }));
  }, [widgetsQuery.data]);
  const widgetsReady = !widgetsQuery.isLoading;
  const enabled = (id: string) => widgets.find((item) => item.id === id)?.enabled !== false;

  const canReadContacts = hasPermission(PERMISSIONS.CONTACTS.READ);
  const canReadActivities = hasPermission(PERMISSIONS.ACTIVITIES.READ);
  const canReadDeals = hasPermission(PERMISSIONS.DEALS.READ);
  const canCustomize = hasPermission(PERMISSIONS.DASHBOARD.CUSTOMIZE);
  const canGenerateAi = canReadDeals && hasPermission(PERMISSIONS.AI.GENERATE);

  const kpis = useDashboardKpisQuery(range, { enabled: widgetsReady && enabled('w-kpis') });
  const revenue = useRevenueChartQuery(range, { enabled: widgetsReady && enabled('w-revenue') });
  const funnel = useSalesFunnelQuery({ enabled: widgetsReady && enabled('w-funnel') });
  const conversions = useLeadConversionsQuery(range, {
    enabled: widgetsReady && enabled('w-conversions'),
  });
  const summary = useActivitiesSummaryQuery(range, {
    enabled: widgetsReady && enabled('w-activity'),
  });
  const deals = useRecentDealsQuery(range, { enabled: widgetsReady && enabled('w-deals') });
  const performers = useTopPerformersQuery(range, {
    enabled: widgetsReady && enabled('w-top'),
  });
  const ai = useDashboardAiInsightsQuery({
    enabled: widgetsReady && canGenerateAi && enabled('w-ai'),
  });
  const contacts = useQuery({
    queryKey: ['contacts', 'dashboard-recent'],
    queryFn: () => fetchContactsApi({ page: 1, limit: 5 }),
    enabled: widgetsReady && canReadContacts && enabled('w-contacts'),
    staleTime: 300_000,
  });
  const activityFeed = useQuery({
    queryKey: ['activities', 'dashboard-recent'],
    queryFn: () => fetchActivitiesPageApi({ page: 1, limit: 5 }),
    enabled: widgetsReady && canReadActivities && enabled('w-activity'),
    staleTime: 300_000,
  });
  const saveWidgets = useSaveCustomWidgetsMutation();

  const formatter = useMemo(() => new Intl.NumberFormat(
    kpis.data?.locale ?? DEFAULT_DASHBOARD_LOCALE,
    {
      style: 'currency',
      currency: kpis.data?.currency ?? DEFAULT_DASHBOARD_CURRENCY,
      maximumFractionDigits: 0,
    },
  ), [kpis.data?.currency, kpis.data?.locale]);
  const formatCurrency = (value: number) => formatter.format(value);

  const setRange = (value: string) => {
    if (!isDashboardRange(value)) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set('range', value);
    router.replace(`${pathname}?${params}`, { scroll: false });
  };

  const refresh = async () => {
    setFeedback(null);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.all }),
      canReadContacts
        ? queryClient.invalidateQueries({ queryKey: ['contacts', 'dashboard-recent'] })
        : Promise.resolve(),
      canReadActivities
        ? queryClient.invalidateQueries({ queryKey: ['activities', 'dashboard-recent'] })
        : Promise.resolve(),
    ]);
    setFeedback('Dashboard data refreshed.');
  };

  const save = async () => {
    setWidgetError(null);
    try {
      await saveWidgets.mutateAsync(draft ?? widgets);
      setFeedback('Dashboard preferences saved.');
      setCustomizing(false);
    } catch {
      setWidgetError('Dashboard preferences could not be saved. Please try again.');
    }
  };

  const loading = [kpis, revenue, funnel, conversions, summary, deals, performers]
    .some((query) => query.isFetching);

  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-3 pb-8">
      <h1 className="sr-only">Dashboard</h1>

      <section
        aria-label="Dashboard controls"
        className="flex flex-wrap items-center justify-end gap-2"
      >
        <Select value={rangeKey} onValueChange={setRange}>
          <SelectTrigger size="sm" className="min-w-36 bg-white" aria-label="Dashboard date range">
            <CalendarRange className="size-3.5" aria-hidden="true" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DASHBOARD_RANGES.map((item) => (
              <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" size="sm" variant="outline" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw className={cn('size-3.5 sm:mr-1.5', loading && 'animate-spin')} aria-hidden="true" />
          <span className="hidden sm:inline">Refresh</span>
        </Button>
        {canCustomize && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              setDraft(widgets);
              setWidgetError(null);
              setCustomizing(true);
            }}
          >
            <SlidersHorizontal className="size-3.5 sm:mr-1.5" aria-hidden="true" />
            <span className="hidden sm:inline">Customize</span>
          </Button>
        )}
        {canReadDeals && (
          <Button asChild size="sm">
            <Link href="/deals">
              Open deals <ArrowUpRight className="ml-1.5 size-3.5" aria-hidden="true" />
            </Link>
          </Button>
        )}
      </section>

      {feedback && (
        <div
          role="status"
          className="flex items-center justify-between rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-800"
        >
          <span>{feedback}</span>
          <button
            type="button"
            className="rounded px-1.5 py-0.5 hover:bg-blue-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            onClick={() => setFeedback(null)}
            aria-label="Dismiss dashboard message"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid items-stretch gap-3 xl:grid-cols-[minmax(0,2.45fr)_minmax(270px,0.8fr)]">
        <div className="min-w-0 space-y-3">
          {enabled('w-kpis') && (
            <DashboardKpiGrid
              data={kpis.data}
              isLoading={!widgetsReady || kpis.isLoading}
              isError={kpis.isError}
              onRetry={() => void kpis.refetch()}
              formatCurrency={formatCurrency}
            />
          )}
          <section className="grid min-w-0 gap-3 lg:grid-cols-2" aria-label="Sales analytics">
            {enabled('w-funnel') && (
              <PipelineCard
                data={funnel.data ?? []}
                isLoading={!widgetsReady || funnel.isLoading}
                isError={funnel.isError}
                onRetry={() => void funnel.refetch()}
                formatCurrency={formatCurrency}
              />
            )}
            {enabled('w-revenue') && (
              <RevenueTrendCard
                data={revenue.data}
                isLoading={!widgetsReady || revenue.isLoading}
                isError={revenue.isError}
                onRetry={() => void revenue.refetch()}
                formatCurrency={formatCurrency}
              />
            )}
          </section>
        </div>
        <aside className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-1" aria-label="Contacts and activity">
          {canReadContacts && enabled('w-contacts') && (
            <RecentContactsCard
              contacts={contacts.data ?? []}
              isLoading={!widgetsReady || contacts.isLoading}
              isError={contacts.isError}
              onRetry={() => void contacts.refetch()}
            />
          )}
          {canReadActivities && enabled('w-activity') && (
            <RecentActivityCard
              activities={activityFeed.data?.items ?? []}
              isLoading={!widgetsReady || activityFeed.isLoading}
              isError={activityFeed.isError}
              onRetry={() => void activityFeed.refetch()}
            />
          )}
        </aside>
      </div>

      {enabled('w-deals') && (
        <DashboardDealsTable
          deals={deals.data ?? []}
          isLoading={!widgetsReady || deals.isLoading}
          isError={deals.isError}
          onRetry={() => void deals.refetch()}
          formatCurrency={formatCurrency}
        />
      )}

      <section className="grid items-start gap-3 lg:grid-cols-3" aria-label="Additional dashboard insights">
        {enabled('w-conversions') && (
          <LeadConversionCard
            data={conversions.data ?? []}
            isLoading={!widgetsReady || conversions.isLoading}
            isError={conversions.isError}
            onRetry={() => void conversions.refetch()}
          />
        )}
        {enabled('w-activity') && (
          <ActivitySummaryCard
            data={summary.data}
            isLoading={!widgetsReady || summary.isLoading}
            isError={summary.isError}
            onRetry={() => void summary.refetch()}
          />
        )}
        {enabled('w-top') && (
          <TopPerformersCard
            performers={performers.data ?? []}
            isLoading={!widgetsReady || performers.isLoading}
            isError={performers.isError}
            onRetry={() => void performers.refetch()}
            formatCurrency={formatCurrency}
          />
        )}
      </section>

      {canGenerateAi && enabled('w-ai') && (
        <DashboardAiPanel
          data={ai.data}
          isLoading={!widgetsReady || ai.isLoading}
          isError={ai.isError}
          onRetry={() => void ai.refetch()}
        />
      )}

      <ModalShell
        isOpen={customizing}
        onClose={() => setCustomizing(false)}
        size="md"
        title="Customize dashboard"
      >
        <p className="text-sm text-slate-500">Choose the sections that are most useful to your workflow.</p>
        {widgetError && (
          <div
            role="alert"
            aria-live="assertive"
            className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-800"
          >
            {widgetError}
          </div>
        )}
        <div className="mt-4 max-h-80 space-y-2 overflow-y-auto">
          {(draft ?? widgets).map((widget) => {
            const unavailable = (widget.id === 'w-contacts' && !canReadContacts)
              || (widget.id === 'w-ai' && !canGenerateAi);
            return (
              <div key={widget.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                <label
                  htmlFor={`widget-${widget.id}`}
                  className={cn('text-sm font-medium text-slate-800', unavailable && 'text-slate-400')}
                >
                  {widget.title}
                  {unavailable && <span className="ml-2 text-xs font-normal">Permission required</span>}
                </label>
                <Switch
                  id={`widget-${widget.id}`}
                  checked={widget.enabled && !unavailable}
                  disabled={unavailable}
                  onCheckedChange={(value) => setDraft((current) => (
                    current ?? widgets
                  ).map((item) => item.id === widget.id ? { ...item, enabled: value } : item))}
                />
              </div>
            );
          })}
        </div>
        <div className="mt-5 flex justify-end gap-2 border-t border-slate-100 pt-4">
          <Button type="button" variant="ghost" onClick={() => setCustomizing(false)}>Cancel</Button>
          <Button type="button" onClick={() => void save()} disabled={saveWidgets.isPending}>
            {saveWidgets.isPending ? 'Saving…' : 'Save preferences'}
          </Button>
        </div>
      </ModalShell>
    </div>
  );
}
