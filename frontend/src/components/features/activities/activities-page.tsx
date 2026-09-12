'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Activity } from 'lucide-react';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { useDebouncedValue } from '@/hooks/use-debounced-value';
import {
  ACTIVITY_MODULES,
  type ActivityItem,
  type ActivityModule,
  useActivitiesPageQuery,
} from '@/lib/api/activities';
import { getErrorMessage } from '@/lib/utils';

const MODULE_LABELS: Record<ActivityModule, string> = {
  leads: 'Leads',
  deals: 'Deals',
  tasks: 'Tasks',
  meetings: 'Meetings',
  calls: 'Calls',
  emails: 'Emails',
  notes: 'Notes',
  calendar: 'Calendar',
  whatsapp: 'WhatsApp',
};

const columns: readonly DataTableColumn<ActivityItem>[] = [
  {
    id: 'activity',
    header: 'ACTIVITY',
    cell: (item) => (
      <div className="min-w-56">
        <p className="font-semibold text-slate-900">{item.action}</p>
        <p className="max-w-lg truncate text-xs text-slate-500">
          {item.description || 'No additional details'}
        </p>
      </div>
    ),
  },
  {
    id: 'module',
    header: 'MODULE',
    cell: (item) => (
      <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
        {MODULE_LABELS[item.module]}
      </span>
    ),
  },
  {
    id: 'entity',
    header: 'RELATED RECORD',
    cell: (item) => (
      <span className="capitalize text-slate-700">{item.entity_type.replaceAll('_', ' ')}</span>
    ),
  },
  {
    id: 'occurred_at',
    header: 'DATE',
    cell: (item) => new Date(item.occurred_at).toLocaleString(),
  },
];

export default function ActivitiesPage(): React.JSX.Element {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [module, setModule] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const limit = 20;
  const query = useActivitiesPageQuery({
    page,
    limit,
    module: module ? (module as ActivityModule) : undefined,
    search: debouncedSearch || undefined,
  });
  const total = query.data?.total ?? 0;

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <Activity className="size-7 text-blue-600" />
          Activities
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Review tenant activity across CRM records and communication channels.
        </p>
      </div>

      {query.isError && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {getErrorMessage(query.error, 'Unable to load activities.')}
        </div>
      )}

      {!query.isError && (
        <DataTable
          columns={columns}
          data={query.data?.items ?? []}
          getRowKey={(item) => item.id}
          onRowClick={(item) => router.push(item.href)}
          emptyTitle="No activities found"
          emptyDescription="Activity appears here as your team works across CRM modules."
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          searchPlaceholder="Search activity..."
          filters={[
            {
              label: 'Module',
              value: module,
              onChange: (value) => {
                setModule(value);
                setPage(1);
              },
              options: ACTIVITY_MODULES.map((value) => ({
                label: MODULE_LABELS[value],
                value,
              })),
            },
          ]}
          hasActiveFilters={Boolean(module || search)}
          onClearFilters={() => {
            setModule('');
            setSearch('');
            setPage(1);
          }}
          isLoading={query.isLoading}
          pagination={{
            pageIndex: page - 1,
            pageCount: Math.max(1, Math.ceil(total / limit)),
            onPageChange: (nextPage) => setPage(nextPage + 1),
            totalRecords: total,
          }}
        />
      )}
    </div>
  );
}
