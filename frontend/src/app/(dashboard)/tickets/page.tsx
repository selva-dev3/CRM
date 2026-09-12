'use client';

import { type FormEvent, useState } from 'react';
import { LifeBuoy, Plus } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { EntityReferenceSelect } from '@/components/common/entity-reference-select';
import { ModalShell } from '@/components/common/modal-shell';
import { ModuleError } from '@/components/common/module-page-state';
import { PermissionGate } from '@/components/common/permission-gate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { type Ticket, useCreateTicket, useDeleteTicket, useTickets, useUpdateTicket } from '@/lib/api/crm-extensions';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const EMPTY_FORM = { subject: '', description: '', priority: 'Medium', contact_id: '', company_id: '' };

export default function TicketsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const query = useTickets(page, search, status);
  const create = useCreateTicket();
  const update = useUpdateTicket();
  const remove = useDeleteTicket();

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await create.mutateAsync({ ...form, contact_id: form.contact_id || null, company_id: form.company_id || null });
      setOpen(false); setForm(EMPTY_FORM); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not create ticket.'));
    }
  }

  const columns: DataTableColumn<Ticket>[] = [
    { id: 'number', header: 'TICKET', cell: (item) => <div><strong>{item.ticket_number}</strong><p className="text-xs text-slate-500">{item.subject}</p></div> },
    { id: 'status', header: 'STATUS', cell: (item) => item.status },
    { id: 'priority', header: 'PRIORITY', cell: (item) => item.priority },
    { id: 'created', header: 'CREATED', cell: (item) => new Date(item.created_at).toLocaleDateString() },
  ];

  return <div className="space-y-6 pb-12">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-bold"><LifeBuoy className="text-indigo-600" />Tickets</h1><p className="text-sm text-slate-500">Track customer requests, ownership, SLA, and resolution.</p></div><PermissionGate permission={PERMISSIONS.TICKETS.CREATE}><Button onClick={() => setOpen(true)}><Plus />Create ticket</Button></PermissionGate></header>
    {error && <ModuleError message={error} />}{query.isError && <ModuleError message="Tickets could not be loaded." retry={() => query.refetch()} />}
    <DataTable columns={columns} data={query.data?.items ?? []} getRowKey={(item) => item.id} onRowClick={(item) => router.push(`/tickets/${item.id}`)} emptyTitle="No tickets" emptyDescription="Create the first support ticket." searchValue={search} onSearchChange={(value) => { setSearch(value); setPage(1); }} statusFilter={{ value: status, options: [{ label: 'All', value: '' }, { label: 'New', value: 'New' }, { label: 'Open', value: 'Open' }, { label: 'Pending', value: 'Pending' }, { label: 'Resolved', value: 'Resolved' }, { label: 'Closed', value: 'Closed' }], onChange: (value) => { setStatus(value); setPage(1); } }} isLoading={query.isLoading} pagination={{ pageIndex: page - 1, pageCount: Math.max(1, Math.ceil((query.data?.total ?? 0) / 20)), totalRecords: query.data?.total, onPageChange: (next) => setPage(next + 1) }} actions={(item) => [{ label: item.status === 'Resolved' ? 'Reopen' : 'Resolve', permission: PERMISSIONS.TICKETS.UPDATE, onClick: () => update.mutate({ id: item.id, payload: { status: item.status === 'Resolved' ? 'Open' : 'Resolved' } }) }, { label: 'Archive', variant: 'destructive', permission: PERMISSIONS.TICKETS.DELETE, onClick: () => remove.mutate(item.id) }]} />
    <ModalShell isOpen={open} onClose={() => setOpen(false)} title="Create support ticket" footer={<><Button variant="outline" type="button" onClick={() => setOpen(false)}>Cancel</Button><Button form="ticket-form" disabled={create.isPending}>Create ticket</Button></>}>
      <form id="ticket-form" onSubmit={submit} className="space-y-4 py-4"><Input required aria-label="Ticket subject" placeholder="Subject" value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} /><textarea required aria-label="Ticket description" className="min-h-28 w-full rounded-md border p-3 text-sm" placeholder="Describe the customer request" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /><select aria-label="Ticket priority" className="h-10 w-full rounded-md border px-3" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}><option>Low</option><option>Medium</option><option>High</option><option>Urgent</option></select><EntityReferenceSelect entityType="Contact" value={form.contact_id} onChange={(id) => setForm({ ...form, contact_id: id })} /><EntityReferenceSelect entityType="Company" value={form.company_id} onChange={(id) => setForm({ ...form, company_id: id })} /></form>
    </ModalShell>
  </div>;
}
