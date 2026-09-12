'use client';

import { type FormEvent, useState } from 'react';
import { Plus, Workflow } from 'lucide-react';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ModalShell } from '@/components/common/modal-shell';
import { ModuleError } from '@/components/common/module-page-state';
import { PermissionGate } from '@/components/common/permission-gate';
import { UserSelect } from '@/components/common/user-select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { type WorkflowDefinition, useCreateWorkflow, useDeleteWorkflow, useUpdateWorkflow, useWorkflowRuns, useWorkflows } from '@/lib/api/crm-extensions';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const INITIAL = { name: '', description: '', module: 'leads', trigger: 'record.created', action: 'notification', field: 'status', value: '', title: 'Follow up', userId: '', email: '', body: '', integrationId: '', conditionField: '', conditionOperator: 'equals', conditionValue: '' };

export default function WorkflowsPage() {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState(INITIAL);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDefinition | null>(null);
  const query = useWorkflows();
  const create = useCreateWorkflow();
  const update = useUpdateWorkflow();
  const remove = useDeleteWorkflow();
  const runs = useWorkflowRuns(selectedWorkflow?.id ?? '');

  async function submit(event: FormEvent) {
    event.preventDefault();
    const actions: Record<string, unknown>[] = [];
    if (form.action === 'update_field') actions.push({ type: 'update_field', field: form.field, value: form.value });
    else if (form.action === 'create_task') actions.push({ type: 'create_task', title: form.title, description: form.body || null, due_days: 1, assigned_to: form.userId || null });
    else if (form.action === 'assign') actions.push({ type: 'assign', user_id: form.userId });
    else if (form.action === 'email') actions.push({ type: 'email', to_email: form.email, subject: form.title, body: form.body });
    else if (form.action === 'webhook') actions.push({ type: 'webhook', integration_id: form.integrationId });
    else actions.push({ type: 'notification', user_id: form.userId || null, title: form.title, message: form.body || form.description || form.name });
    const conditions = form.conditionField ? [{ field: form.conditionField, operator: form.conditionOperator, value: form.conditionOperator === 'changed' ? null : form.conditionValue }] : [];
    try {
      await create.mutateAsync({ name: form.name, description: form.description || null, module: form.module, trigger: form.trigger, conditions, actions, is_active: false });
      setOpen(false); setForm(INITIAL); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not create workflow.'));
    }
  }

  const columns: DataTableColumn<WorkflowDefinition>[] = [
    { id: 'name', header: 'WORKFLOW', cell: (item) => <div><strong>{item.name}</strong><p className="text-xs text-slate-500">{item.description || 'No description'}</p></div> },
    { id: 'module', header: 'MODULE', cell: (item) => <span className="capitalize">{item.module}</span> },
    { id: 'trigger', header: 'TRIGGER', cell: (item) => item.trigger.replaceAll('.', ' ') },
    { id: 'status', header: 'STATUS', cell: (item) => <span className={item.is_active ? 'text-emerald-600' : 'text-slate-500'}>{item.is_active ? 'Active' : 'Inactive'}</span> },
  ];

  const needsUser = ['notification', 'create_task', 'assign'].includes(form.action);
  async function toggleWorkflow(item: WorkflowDefinition) {
    try {
      await update.mutateAsync({ id: item.id, payload: { is_active: !item.is_active } });
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not update workflow status.'));
    }
  }

  async function deleteWorkflow(item: WorkflowDefinition) {
    try {
      await remove.mutateAsync(item.id);
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not delete workflow.'));
    }
  }
  return <div className="space-y-6 pb-12">
    <header className="flex flex-wrap justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-bold"><Workflow className="text-indigo-600" />Workflows / Automation</h1><p className="text-sm text-slate-500">Automate record updates, assignment, tasks, notifications, email, and webhooks.</p></div><PermissionGate permission={PERMISSIONS.WORKFLOWS.CREATE}><Button onClick={() => setOpen(true)}><Plus />New workflow</Button></PermissionGate></header>
    {error && <ModuleError message={error} />}{query.isError && <ModuleError message="Workflows could not be loaded." retry={() => query.refetch()} />}
    <DataTable columns={columns} data={query.data?.items ?? []} getRowKey={(item) => item.id} emptyTitle="No workflows" emptyDescription="Create an automation rule." isLoading={query.isLoading} actions={(item) => [{ label: 'View runs', permission: PERMISSIONS.WORKFLOWS.READ, onClick: () => setSelectedWorkflow(item) }, { label: item.is_active ? 'Deactivate' : 'Activate', permission: PERMISSIONS.WORKFLOWS.UPDATE, onClick: () => void toggleWorkflow(item) }, { label: 'Delete', variant: 'destructive', permission: PERMISSIONS.WORKFLOWS.DELETE, onClick: () => void deleteWorkflow(item) }]} />
    <ModalShell isOpen={open} onClose={() => setOpen(false)} title="Create workflow" footer={<><Button variant="outline" type="button" onClick={() => setOpen(false)}>Cancel</Button><Button form="workflow-form" disabled={create.isPending}>Save workflow</Button></>}>
      <form id="workflow-form" onSubmit={submit} className="space-y-4 py-4"><Input required aria-label="Workflow name" placeholder="Workflow name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /><Input aria-label="Workflow description" placeholder="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /><div className="grid gap-3 sm:grid-cols-2"><select aria-label="Workflow module" className="h-10 rounded-md border px-3" value={form.module} onChange={(event) => setForm({ ...form, module: event.target.value })}>{['leads', 'deals', 'tasks', 'projects', 'tickets'].map((value) => <option key={value}>{value}</option>)}</select><select aria-label="Workflow trigger" className="h-10 rounded-md border px-3" value={form.trigger} onChange={(event) => setForm({ ...form, trigger: event.target.value })}><option value="record.created">Record created</option><option value="record.updated">Record updated</option><option value="record.status_changed">Status changed</option></select></div><fieldset className="space-y-3 rounded-lg border p-3"><legend className="px-1 text-sm font-semibold">Optional condition</legend><div className="grid gap-3 sm:grid-cols-3"><Input aria-label="Condition field" placeholder="Field (for example status)" value={form.conditionField} onChange={(event) => setForm({ ...form, conditionField: event.target.value })} /><select aria-label="Condition operator" className="h-10 rounded-md border px-3" value={form.conditionOperator} onChange={(event) => setForm({ ...form, conditionOperator: event.target.value })}><option value="equals">Equals</option><option value="not_equals">Does not equal</option><option value="changed">Changed</option></select>{form.conditionOperator !== 'changed' && <Input aria-label="Condition value" placeholder="Value" value={form.conditionValue} onChange={(event) => setForm({ ...form, conditionValue: event.target.value })} />}</div></fieldset><select aria-label="Workflow action" className="h-10 w-full rounded-md border px-3" value={form.action} onChange={(event) => setForm({ ...form, action: event.target.value })}><option value="notification">Send notification</option><option value="create_task">Create task</option><option value="assign">Assign record</option><option value="update_field">Update field</option><option value="email">Queue email</option><option value="webhook">Queue integration webhook</option></select>{form.action === 'update_field' && <div className="grid grid-cols-2 gap-3"><Input required placeholder="Field" value={form.field} onChange={(event) => setForm({ ...form, field: event.target.value })} /><Input placeholder="Value" value={form.value} onChange={(event) => setForm({ ...form, value: event.target.value })} /></div>}{needsUser && <div><label className="mb-1 block text-sm font-medium">Target user {form.action === 'assign' ? '*' : '(optional)'}</label><UserSelect value={form.userId} onChange={(userId) => setForm({ ...form, userId })} /></div>}{form.action === 'email' && <Input required type="email" aria-label="Recipient email" placeholder="Recipient email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />}{form.action === 'webhook' && <Input required aria-label="Integration ID" placeholder="Connected integration ID" value={form.integrationId} onChange={(event) => setForm({ ...form, integrationId: event.target.value })} />}{!['assign', 'update_field', 'webhook'].includes(form.action) && <Input required aria-label="Action title" placeholder={form.action === 'email' ? 'Email subject' : 'Action title'} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />}{['email', 'notification', 'create_task'].includes(form.action) && <textarea required={form.action === 'email'} aria-label="Action message" className="min-h-24 w-full rounded-md border p-3 text-sm" placeholder={form.action === 'email' ? 'Email body' : 'Message or task description'} value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} />}</form>
    </ModalShell>
    <ModalShell isOpen={Boolean(selectedWorkflow)} onClose={() => setSelectedWorkflow(null)} title={`${selectedWorkflow?.name ?? 'Workflow'} runs`}><div className="space-y-3 py-4">{runs.isLoading ? <p className="text-sm text-slate-500">Loading workflow runs…</p> : runs.isError ? <ModuleError message="Workflow runs could not be loaded." retry={() => runs.refetch()} /> : runs.data?.length ? runs.data.map((run) => <article key={run.id} className="rounded-lg border p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className={`text-sm font-semibold ${run.status === 'Completed' ? 'text-emerald-700' : run.status === 'Failed' ? 'text-rose-700' : 'text-amber-700'}`}>{run.status}</span><time className="text-xs text-slate-500">{new Date(run.started_at).toLocaleString()}</time></div>{run.error && <p role="alert" className="mt-2 text-sm text-rose-700">{run.error}</p>}<p className="mt-2 text-xs text-slate-500">{run.action_results.length} action result{run.action_results.length === 1 ? '' : 's'}</p></article>) : <p className="rounded-lg border border-dashed p-4 text-sm text-slate-500">This workflow has not run yet.</p>}</div></ModalShell>
  </div>;
}
