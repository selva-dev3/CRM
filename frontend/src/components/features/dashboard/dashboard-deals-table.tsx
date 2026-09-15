'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowUpRight } from 'lucide-react';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { Button, Card } from '@/components/ui';
import type { RecentDealItem } from '@/lib/api/dashboard';
import { cn } from '@/lib/utils';

const STAGE_TONES: Record<string, string> = {
  Prospecting: 'border-sky-100 bg-sky-50 text-sky-700',
  Qualification: 'border-indigo-100 bg-indigo-50 text-indigo-700',
  Proposal: 'border-violet-100 bg-violet-50 text-violet-700',
  Negotiation: 'border-amber-100 bg-amber-50 text-amber-700',
  'Closed Won': 'border-emerald-100 bg-emerald-50 text-emerald-700',
  'Closed Lost': 'border-rose-100 bg-rose-50 text-rose-700',
};

export function formatDashboardDealDate(value: string) {
  const calendarDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!calendarDate) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value || 'Recently updated';
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(parsed);
  }

  const [, year, month, day] = calendarDate;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day));
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed);
}

export function DashboardDealsTable({
  deals,
  isLoading,
  isError,
  onRetry,
  formatCurrency,
}: {
  deals: RecentDealItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  formatCurrency: (value: number) => string;
}) {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [stage, setStage] = useState('all');
  const [sort, setSort] = useState('updated');
  const stages = useMemo(
    () => Array.from(new Set(deals.map((deal) => deal.stage).filter(Boolean))) as string[],
    [deals],
  );
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const result = deals.filter((deal) => (
      (!term || deal.title.toLowerCase().includes(term) || deal.owner?.toLowerCase().includes(term))
      && (stage === 'all' || deal.stage === stage)
    ));
    return [...result].sort((a, b) => {
      if (sort === 'amount-desc') return b.amount - a.amount;
      if (sort === 'amount-asc') return a.amount - b.amount;
      return b.updated_at.localeCompare(a.updated_at);
    });
  }, [deals, search, sort, stage]);

  const columns = useMemo<readonly DataTableColumn<RecentDealItem>[]>(() => [
    {
      id: 'title',
      header: 'Deal name',
      cell: (deal) => (
        <Link
          href={`/deals/${deal.deal_id}`}
          className="font-medium text-slate-900 hover:text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {deal.title}
        </Link>
      ),
    },
    {
      id: 'owner',
      header: 'Deal owner',
      enableHiding: true,
      cell: (deal) => (
        <span className="inline-flex items-center gap-2 text-slate-700">
          <span className="flex size-6 items-center justify-center rounded-full bg-blue-50 text-[9px] font-semibold text-blue-700">
            {(deal.owner || 'U').slice(0, 1).toUpperCase()}
          </span>
          {deal.owner || 'Unassigned'}
        </span>
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      cell: (deal) => (
        <span className="font-medium text-slate-950 tabular-nums">{formatCurrency(deal.amount)}</span>
      ),
    },
    {
      id: 'updated',
      header: 'Last updated',
      enableHiding: true,
      cell: (deal) => (
        <time
          dateTime={/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(deal.updated_at) ? deal.updated_at : undefined}
          className="whitespace-nowrap text-slate-600"
        >
          {formatDashboardDealDate(deal.updated_at)}
        </time>
      ),
    },
    {
      id: 'stage',
      header: 'Deal stage',
      enableHiding: true,
      cell: (deal) => (
        <span
          className={cn(
            'inline-flex rounded border px-2 py-1 text-[10px] font-medium',
            STAGE_TONES[deal.stage ?? 'Prospecting'] ?? 'border-slate-200 bg-slate-50 text-slate-700',
          )}
        >
          {deal.stage || 'Prospecting'}
        </span>
      ),
    },
  ], [formatCurrency]);

  return (
    <Card className="overflow-hidden shadow-none">
      {isError ? (
        <div role="alert" className="flex min-h-40 flex-col items-center justify-center gap-3 p-5 text-center">
          <p className="text-sm font-medium text-slate-700">Recent deals could not be loaded.</p>
          <Button size="sm" variant="outline" onClick={onRetry}>Try again</Button>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          getRowKey={(deal) => deal.deal_id}
          onRowClick={(deal) => router.push(`/deals/${deal.deal_id}`)}
          emptyTitle="No deals found"
          emptyDescription={
            search || stage !== 'all'
              ? 'Try changing your search or stage filter.'
              : 'No deals were updated in this period.'
          }
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search deals or owners..."
          statusFilter={{
            value: stage,
            options: [{ label: 'All stages', value: 'all' }, ...stages.map((value) => ({ label: value, value }))],
            onChange: setStage,
          }}
          sortOptions={{
            value: sort,
            options: [
              { label: 'Recently updated', value: 'updated' },
              { label: 'Amount: high to low', value: 'amount-desc' },
              { label: 'Amount: low to high', value: 'amount-asc' },
            ],
            onChange: setSort,
          }}
          hasActiveFilters={Boolean(search) || stage !== 'all'}
          onClearFilters={() => {
            setSearch('');
            setStage('all');
          }}
          leftActions={<h2 className="mr-2 text-base font-semibold text-slate-950">Deals</h2>}
          toolbarActions={(
            <Button asChild size="sm" variant="outline" className="h-9">
              <Link href="/deals">View all deals <ArrowUpRight className="ml-1 size-3.5" /></Link>
            </Button>
          )}
          actions={(deal) => [{
            id: 'open',
            label: 'Open deal',
            onClick: () => router.push(`/deals/${deal.deal_id}`),
          }]}
          pagination={{ pageSize: 5 }}
          isLoading={isLoading}
          loadingLabel="Loading recent deals"
          tableClassName="min-w-[720px]"
          transparent
        />
      )}
    </Card>
  );
}
