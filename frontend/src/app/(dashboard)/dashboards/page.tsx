'use client';

import { type FormEvent, useState } from 'react';
import { PanelsTopLeft, Plus } from 'lucide-react';
import Link from 'next/link';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ModuleError } from '@/components/common/module-page-state';
import { PermissionGate } from '@/components/common/permission-gate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { type SavedDashboard, useCreateSavedDashboard, useDeleteSavedDashboard, useSavedDashboards, useUpdateSavedDashboard } from '@/lib/api/crm-extensions';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';
import { useAuth } from '@/providers/auth-provider';

const DEFAULT_WIDGETS = ['w-kpis', 'w-funnel', 'w-revenue', 'w-performers', 'w-conversions', 'w-activities', 'w-deals', 'w-ai'].map((id) => ({ id, enabled: true }));

export default function DashboardsPage() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [shared, setShared] = useState(false);
  const [error, setError] = useState('');
  const query = useSavedDashboards();
  const create = useCreateSavedDashboard();
  const update = useUpdateSavedDashboard();
  const remove = useDeleteSavedDashboard();
  const { user } = useAuth();

  async function changeVisibility(item: SavedDashboard) {
    try {
      await update.mutateAsync({ id: item.id, payload: { is_shared: !item.is_shared } });
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not change dashboard visibility.'));
    }
  }

  async function deleteDashboard(item: SavedDashboard) {
    try {
      await remove.mutateAsync(item.id);
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not delete dashboard.'));
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await create.mutateAsync({ name: name.trim(), description: description.trim() || null, is_shared: shared, widgets: DEFAULT_WIDGETS, filters: {} });
      setName(''); setDescription(''); setShared(false); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not create dashboard.'));
    }
  }

  const columns: DataTableColumn<SavedDashboard>[] = [
    { id: 'name', header: 'DASHBOARD', cell: (item) => <div><strong>{item.name}</strong><p className="text-xs text-slate-500">{item.description || 'No description'}</p></div> },
    { id: 'visibility', header: 'VISIBILITY', cell: (item) => item.is_shared ? 'Shared' : 'Private' },
    { id: 'widgets', header: 'WIDGETS', cell: (item) => item.widgets.filter((widget) => widget.enabled !== false).length },
    { id: 'updated', header: 'UPDATED', cell: (item) => new Date(item.updated_at).toLocaleDateString() },
  ];

  return <div className="space-y-6 pb-12"><header><h1 className="flex items-center gap-2 text-2xl font-bold"><PanelsTopLeft className="text-indigo-600" />Dashboards</h1><p className="text-sm text-slate-500">Save and share reusable views of existing executive metrics.</p></header><PermissionGate permission={PERMISSIONS.DASHBOARD.CUSTOMIZE}><form onSubmit={submit} className="grid gap-3 rounded-xl border bg-white p-4 md:grid-cols-[1fr_2fr_auto_auto]"><Input required aria-label="Dashboard name" placeholder="Dashboard name" value={name} onChange={(event) => setName(event.target.value)} /><Input aria-label="Dashboard description" placeholder="Description" value={description} onChange={(event) => setDescription(event.target.value)} /><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={shared} onChange={(event) => setShared(event.target.checked)} />Share</label><Button disabled={create.isPending}><Plus />Create</Button></form></PermissionGate>{error && <ModuleError message={error} />}{query.isError && <ModuleError message="Dashboards could not be loaded." retry={() => query.refetch()} />}<div className="rounded-xl border bg-white p-3"><Link href="/dashboard" className="text-sm font-semibold text-indigo-700 hover:underline">Open executive dashboard</Link></div><DataTable columns={columns} data={query.data?.items ?? []} getRowKey={(item) => item.id} emptyTitle="No saved dashboards" emptyDescription="Create a named dashboard layout." isLoading={query.isLoading} actions={(item) => item.owner_id === user?.id ? [{ label: item.is_shared ? 'Make private' : 'Share', permission: PERMISSIONS.DASHBOARD.CUSTOMIZE, onClick: () => void changeVisibility(item) }, { label: 'Delete', variant: 'destructive', permission: PERMISSIONS.DASHBOARD.CUSTOMIZE, onClick: () => void deleteDashboard(item) }] : []} /></div>;
}
