'use client';

import { type FormEvent, useState } from 'react';
import { Plus, Trash2, Users } from 'lucide-react';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ModalShell } from '@/components/common/modal-shell';
import { ModuleError } from '@/components/common/module-page-state';
import { PermissionGate } from '@/components/common/permission-gate';
import { UserSelect } from '@/components/common/user-select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  type Team,
  useAddTeamMember,
  useCreateTeam,
  useDeleteTeam,
  useRemoveTeamMember,
  useTeam,
  useTeams,
} from '@/lib/api/crm-extensions';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

export default function TeamsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const [memberId, setMemberId] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [error, setError] = useState('');
  const query = useTeams(page, search);
  const team = useTeam(selectedTeamId);
  const create = useCreateTeam();
  const remove = useDeleteTeam();
  const addMember = useAddTeamMember();
  const removeMember = useRemoveTeamMember();

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await create.mutateAsync({ name: name.trim(), description: description.trim() || undefined });
      setName(''); setDescription(''); setError(''); setIsCreateOpen(false);
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not create team.'));
    }
  }

  async function submitMember(event: FormEvent) {
    event.preventDefault();
    if (!memberId || !selectedTeamId) return;
    try {
      await addMember.mutateAsync({ teamId: selectedTeamId, userId: memberId, isPrimary });
      setMemberId(''); setIsPrimary(false); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not add the team member.'));
    }
  }

  const columns: DataTableColumn<Team>[] = [
    { id: 'name', header: 'TEAM', cell: (item) => <div><strong>{item.name}</strong><p className="text-xs text-slate-500">{item.description || 'No description'}</p></div> },
    { id: 'members', header: 'MEMBERS', cell: (item) => item.member_count },
    { id: 'status', header: 'STATUS', cell: (item) => <span className={item.is_active ? 'text-emerald-600' : 'text-slate-500'}>{item.is_active ? 'Active' : 'Inactive'}</span> },
  ];

  return <div className="space-y-6 pb-12">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-bold"><Users className="text-indigo-600" />Teams</h1><p className="text-sm text-slate-500">Group users for assignment, routing, and record access.</p></div><PermissionGate permission={PERMISSIONS.TEAMS.CREATE}><Button onClick={() => { setName(''); setDescription(''); setError(''); setIsCreateOpen(true); }}><Plus />Create team</Button></PermissionGate></header>
    {error && <ModuleError message={error} />}{query.isError && <ModuleError message="Teams could not be loaded." retry={() => query.refetch()} />}
    <DataTable columns={columns} data={query.data?.items ?? []} getRowKey={(item) => item.id} emptyTitle="No teams" emptyDescription="Create a team to organize users." searchValue={search} onSearchChange={(value) => { setSearch(value); setPage(1); }} isLoading={query.isLoading} pagination={{ pageIndex: page - 1, pageCount: Math.max(1, Math.ceil((query.data?.total ?? 0) / 20)), totalRecords: query.data?.total, onPageChange: (next) => setPage(next + 1) }} actions={(item) => [{ label: 'Manage members', permission: PERMISSIONS.TEAMS.MANAGE_MEMBERS, onClick: () => setSelectedTeamId(item.id) }, { label: 'Delete', variant: 'destructive', permission: PERMISSIONS.TEAMS.DELETE, onClick: () => remove.mutate(item.id) }]} />
    <ModalShell isOpen={Boolean(selectedTeamId)} onClose={() => setSelectedTeamId('')} title={`Manage ${team.data?.name ?? 'team'} members`}>
      <div className="space-y-5 py-4">
        <form onSubmit={submitMember} className="space-y-3 rounded-lg border p-3"><UserSelect value={memberId} onChange={setMemberId} /><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} />Primary team for this user</label><Button disabled={!memberId || addMember.isPending}>Add member</Button></form>
        {team.isLoading && <p className="text-sm text-slate-500">Loading members…</p>}{team.isError && <ModuleError message="Team members could not be loaded." retry={() => team.refetch()} />}{!team.isLoading && !team.data?.members.length && <p className="text-sm text-slate-500">No members in this team.</p>}
        <ul className="divide-y rounded-lg border">{team.data?.members.map((member) => <li key={member.user_id} className="flex items-center justify-between gap-3 p-3"><div className="min-w-0"><p className="truncate font-medium">{member.name}</p><p className="truncate text-xs text-slate-500">{member.email}{member.is_primary ? ' · Primary' : ''}</p></div><Button variant="ghost" size="icon" aria-label={`Remove ${member.name}`} disabled={removeMember.isPending} onClick={() => removeMember.mutate({ teamId: selectedTeamId, userId: member.user_id })}><Trash2 className="size-4 text-rose-600" /></Button></li>)}</ul>
      </div>
    </ModalShell>
    <ModalShell isOpen={isCreateOpen} onClose={() => !create.isPending && setIsCreateOpen(false)} title="Create team" footer={<><Button type="button" variant="outline" disabled={create.isPending} onClick={() => setIsCreateOpen(false)}>Cancel</Button><Button form="create-team-form" disabled={create.isPending}>{create.isPending ? 'Creating…' : 'Create team'}</Button></>}><form id="create-team-form" onSubmit={submit} className="space-y-4 py-4"><div><label htmlFor="team-name" className="mb-1 block text-sm font-medium">Team name</label><Input id="team-name" autoFocus required value={name} onChange={(event) => setName(event.target.value)} /></div><div><label htmlFor="team-description" className="mb-1 block text-sm font-medium">Description</label><Input id="team-description" value={description} onChange={(event) => setDescription(event.target.value)} /></div>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}</form></ModalShell>
  </div>;
}
