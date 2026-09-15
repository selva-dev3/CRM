import Link from 'next/link';
import { Sparkles } from 'lucide-react';

import { Button, Card } from '@/components/ui';
import type { DashboardAiInsights } from '@/lib/api/dashboard';

import {
  DashboardSectionEmpty,
  DashboardSectionError,
  DashboardSectionSkeleton,
} from './dashboard-section-state';

export function DashboardAiPanel({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data?: DashboardAiInsights;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <Card className="border-blue-100 bg-blue-50/60 p-4 shadow-none">
      {isLoading && <DashboardSectionSkeleton className="h-16 bg-white/70" />}
      {isError && (
        <DashboardSectionError message="AI pipeline briefing could not be loaded." onRetry={onRetry} />
      )}
      {!isLoading && !isError && !data && (
        <DashboardSectionEmpty
          title="No AI briefing available"
          description="Recommendations will appear when enough pipeline data is available."
        />
      )}
      {!isError && data && (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white">
              <Sparkles className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-900">AI pipeline briefing</p>
              <p className="mt-0.5 text-xs leading-5 text-slate-600">{data.summary}</p>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai">Open AI intelligence</Link>
            </Button>
          </div>
          {data.insights && data.insights.length > 0 && (
            <div className="grid gap-2 border-t border-blue-100 pt-3 md:grid-cols-2">
              {data.insights.slice(0, 4).map((item) => (
                <div
                  key={`${item.title}-${item.deal_id ?? 'general'}`}
                  className="flex items-start justify-between gap-3 rounded-lg border border-blue-100 bg-white p-3"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">
                      {item.description}
                    </p>
                  </div>
                  {item.action && (
                    <Button asChild size="sm" variant="ghost" className="h-7 shrink-0 px-2 text-[11px]">
                      <Link href={item.deal_id ? `/deals/${item.deal_id}` : '/ai'}>{item.action}</Link>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
          {data.risk_deals && data.risk_deals.length > 0 && (
            <div className="border-t border-blue-100 pt-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Deals requiring attention
              </p>
              <div className="flex flex-wrap gap-2">
                {data.risk_deals.slice(0, 4).map((deal) => (
                  <Link
                    key={deal.id}
                    href={`/deals/${deal.id}`}
                    className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                  >
                    {deal.title} · {deal.stage}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
