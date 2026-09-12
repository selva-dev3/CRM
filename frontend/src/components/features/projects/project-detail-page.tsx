'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, CalendarDays, CheckSquare, CircleDollarSign, FileText, Flag, FolderKanban, Plus, Trash2, UserRound, UsersRound } from 'lucide-react';

import { ConfirmModal } from '@/components/common/confirm-modal';
import { EntityReferenceSelect } from '@/components/common/entity-reference-select';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useAddProjectStakeholderMutation, useDeleteProjectMutation, useProjectQuery, useProjectStakeholdersQuery, useRemoveProjectStakeholderMutation } from '@/lib/api/projects';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';
import { useState } from 'react';

export default function ProjectDetailPage(): React.JSX.Element {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params?.id ?? '');
  const projectQuery = useProjectQuery(projectId);
  const deleteProject = useDeleteProjectMutation();
  const addStakeholder = useAddProjectStakeholderMutation();
  const removeStakeholder = useRemoveProjectStakeholderMutation();
  const { hasPermission } = useHasPermission();
  const canReadContacts = hasPermission(PERMISSIONS.CONTACTS.READ);
  const canUpdateProject = hasPermission(PERMISSIONS.PROJECTS.UPDATE);
  const stakeholders = useProjectStakeholdersQuery(projectId, canReadContacts);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [stakeholderOpen, setStakeholderOpen] = useState(false);
  const [contactId, setContactId] = useState('');
  const [contactLabel, setContactLabel] = useState('');
  const [stakeholderRole, setStakeholderRole] = useState('Stakeholder');
  const [error, setError] = useState<string | null>(null);

  if (projectQuery.isLoading) return <div className="p-8 text-sm text-slate-500">Loading project…</div>;
  if (projectQuery.isError || !projectQuery.data) return <div className="space-y-4 p-6"><Link href="/projects" className="inline-flex items-center gap-2 text-sm text-blue-600"><ArrowLeft className="size-4" />Back to Projects</Link><div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-rose-800">Project not found or no longer accessible.</div></div>;

  const project = projectQuery.data;
  const remove = async () => {
    try {
      await deleteProject.mutateAsync(project.id);
      router.push('/projects');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to delete project.'));
      setConfirmingDelete(false);
    }
  };
  const saveStakeholder = async () => {
    if (!contactId || !stakeholderRole.trim()) return;
    try {
      await addStakeholder.mutateAsync({ projectId, contactId, role: stakeholderRole.trim() });
      setStakeholderOpen(false); setContactId(''); setContactLabel(''); setStakeholderRole('Stakeholder'); setError(null);
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to add project stakeholder.'));
    }
  };

  return <div className="space-y-6 pb-12">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
      <div><Link href="/projects" className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-blue-600"><ArrowLeft className="size-4" />Back to Projects</Link><h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900"><FolderKanban className="size-7 text-blue-600" />{project.name}</h1><p className="mt-2 max-w-3xl text-sm text-slate-600">{project.description || 'No project description.'}</p></div>
      <PermissionGate permission={PERMISSIONS.PROJECTS.DELETE}><Button variant="destructive" onClick={() => setConfirmingDelete(true)}><Trash2 className="size-4" />Delete</Button></PermissionGate>
    </div>
    {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article className="rounded-xl border bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-500">Status</p><p className="mt-2 font-semibold text-slate-900">{project.status}</p></article>
      <article className="rounded-xl border bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-500">Priority</p><p className="mt-2 font-semibold text-slate-900">{project.priority}</p></article>
      <article className="rounded-xl border bg-white p-5"><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><CircleDollarSign className="size-4" />Budget</p><p className="mt-2 font-semibold text-slate-900">{project.budget == null ? 'Not set' : project.budget.toLocaleString()}</p></article>
      <article className="rounded-xl border bg-white p-5"><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><UserRound className="size-4" />Owner</p><p className="mt-2 break-all font-semibold text-slate-900">{project.owner_id || 'Unassigned'}</p></article>
    </div>
    <section className="rounded-xl border bg-white p-6"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-slate-900">Delivery progress</h2><span className="text-sm font-semibold text-blue-700">{project.completion_percentage}%</span></div><div className="h-3 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${project.completion_percentage}%` }} /></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><div><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><CalendarDays className="size-4" />Start date</p><p className="mt-1 text-sm text-slate-900">{project.start_date ? new Date(project.start_date).toLocaleDateString() : 'Not set'}</p></div><div><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><CalendarDays className="size-4" />Due date</p><p className="mt-1 text-sm text-slate-900">{project.due_date ? new Date(project.due_date).toLocaleDateString() : 'Not set'}</p></div></div></section>
    {(project.company_id || project.contact_id || project.originating_deal_id) && <section className="rounded-xl border bg-white p-6"><h2 className="mb-4 font-semibold text-slate-900">CRM relationships</h2><div className="grid gap-3 sm:grid-cols-3">{project.company_id && <Link href={`/companies/${project.company_id}`} className="rounded-lg border p-3 text-sm font-semibold text-indigo-700 hover:border-indigo-300">Open company</Link>}{project.contact_id && <Link href={`/contacts/${project.contact_id}`} className="rounded-lg border p-3 text-sm font-semibold text-indigo-700 hover:border-indigo-300">Open contact</Link>}{project.originating_deal_id && <Link href={`/deals/${project.originating_deal_id}`} className="rounded-lg border p-3 text-sm font-semibold text-indigo-700 hover:border-indigo-300">Open originating deal</Link>}</div></section>}
    {canReadContacts && <section className="rounded-xl border bg-white p-6"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold text-slate-900"><UsersRound className="size-5 text-indigo-600" />Stakeholders</h2><p className="mt-1 text-sm text-slate-500">Contacts involved in delivery, approval, or communication.</p></div>{canUpdateProject && <Button size="sm" onClick={() => setStakeholderOpen(true)}><Plus className="size-4" />Add stakeholder</Button>}</div>{stakeholders.isLoading ? <p className="text-sm text-slate-500">Loading stakeholders…</p> : stakeholders.isError ? <p role="alert" className="text-sm text-rose-700">Stakeholders could not be loaded.</p> : stakeholders.data?.length ? <div className="divide-y rounded-lg border">{stakeholders.data.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 p-3"><div><Link href={`/contacts/${item.contact_id}`} className="font-medium text-indigo-700 hover:underline">{item.contact_id}</Link><p className="text-xs text-slate-500">{item.role}</p></div>{canUpdateProject && <Button variant="ghost" size="sm" disabled={removeStakeholder.isPending} onClick={() => removeStakeholder.mutate({ projectId, stakeholderId: item.id })}>Remove</Button>}</div>)}</div> : <p className="rounded-lg border border-dashed p-4 text-sm text-slate-500">No stakeholders linked to this project.</p>}</section>}
    <section className="grid gap-3 sm:grid-cols-3"><Link href="/project-tasks" className="flex items-center gap-3 rounded-xl border bg-white p-4 font-semibold text-slate-800 hover:border-indigo-300"><CheckSquare className="text-indigo-600"/>Project tasks</Link><Link href="/milestones" className="flex items-center gap-3 rounded-xl border bg-white p-4 font-semibold text-slate-800 hover:border-indigo-300"><Flag className="text-indigo-600"/>Milestones</Link><Link href="/project-documents" className="flex items-center gap-3 rounded-xl border bg-white p-4 font-semibold text-slate-800 hover:border-indigo-300"><FileText className="text-indigo-600"/>Project documents</Link></section>
    <ConfirmModal isOpen={confirmingDelete} onClose={() => setConfirmingDelete(false)} onConfirm={remove} title="Delete project" message={`Delete “${project.name}”? Linked deals and tasks will retain their records but lose this association.`} confirmText="Delete Project" variant="danger" isLoading={deleteProject.isPending} />
    <ModalShell isOpen={stakeholderOpen} onClose={() => setStakeholderOpen(false)} title="Add project stakeholder" footer={<><Button variant="outline" onClick={() => setStakeholderOpen(false)}>Cancel</Button><Button disabled={!contactId || !stakeholderRole.trim() || addStakeholder.isPending} onClick={saveStakeholder}>Add stakeholder</Button></>}><div className="space-y-4 py-4"><div><label className="mb-1 block text-sm font-medium">Contact</label><EntityReferenceSelect entityType="Contact" value={contactId} selectedLabel={contactLabel} onChange={(id, label) => { setContactId(id); setContactLabel(label); }} /></div><div><label htmlFor="stakeholder-role" className="mb-1 block text-sm font-medium">Role</label><Input id="stakeholder-role" maxLength={100} value={stakeholderRole} onChange={(event) => setStakeholderRole(event.target.value)} placeholder="Sponsor, approver, subject expert…" /></div></div></ModalShell>
  </div>;
}
