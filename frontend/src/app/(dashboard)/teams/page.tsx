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
      setName(''); setDescription(''); setError('');
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
    <header><h1 className="flex items-center gap-2 text-2xl font-bold"><Users className="text-indigo-600" />Teams</h1><p className="text-sm text-slate-500">Group users for assignment, routing, and record access.</p></header>
    <PermissionGate permission={PERMISSIONS.TEAMS.CREATE}><form onSubmit={submit} className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-[1fr_2fr_auto]"><Input required aria-label="Team name" placeholder="Team name" value={name} onChange={(event) => setName(event.target.value)} /><Input aria-label="Team description" placeholder="Description" value={description} onChange={(event) => setDescription(event.target.value)} /><Button disabled={create.isPending}><Plus />Create team</Button></form></PermissionGate>
    {error && <ModuleError message={error} />}{query.isError && <ModuleError message="Teams could not be loaded." retry={() => query.refetch()} />}
    <DataTable columns={columns} data={query.data?.items ?? []} getRowKey={(item) => item.id} emptyTitle="No teams" emptyDescription="Create a team to organize users." searchValue={search} onSearchChange={(value) => { setSearch(value); setPage(1); }} isLoading={query.isLoading} pagination={{ pageIndex: page - 1, pageCount: Math.max(1, Math.ceil((query.data?.total ?? 0) / 20)), totalRecords: query.data?.total, onPageChange: (next) => setPage(next + 1) }} actions={(item) => [{ label: 'Manage members', permission: PERMISSIONS.TEAMS.MANAGE_MEMBERS, onClick: () => setSelectedTeamId(item.id) }, { label: 'Delete', variant: 'destructive', permission: PERMISSIONS.TEAMS.DELETE, onClick: () => remove.mutate(item.id) }]} />
    <ModalShell isOpen={Boolean(selectedTeamId)} onClose={() => setSelectedTeamId('')} title={`Manage ${team.data?.name ?? 'team'} members`}>
      <div className="space-y-5 py-4">
        <form onSubmit={submitMember} className="space-y-3 rounded-lg border p-3"><UserSelect value={memberId} onChange={setMemberId} /><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} />Primary team for this user</label><Button disabled={!memberId || addMember.isPending}>Add member</Button></form>
        {team.isLoading && <p className="text-sm text-slate-500">Loading members…</p>}{team.isError && <ModuleError message="Team members could not be loaded." retry={() => team.refetch()} />}{!team.isLoading && !team.data?.members.length && <p className="text-sm text-slate-500">No members in this team.</p>}
        <ul className="divide-y rounded-lg border">{team.data?.members.map((member) => <li key={member.user_id} className="flex items-center justify-between gap-3 p-3"><div className="min-w-0"><p className="truncate font-medium">{member.name}</p><p className="truncate text-xs text-slate-500">{member.email}{member.is_primary ? ' · Primary' : ''}</p></div><Button variant="ghost" size="icon" aria-label={`Remove ${member.name}`} disabled={removeMember.isPending} onClick={() => removeMember.mutate({ teamId: selectedTeamId, userId: member.user_id })}><Trash2 className="size-4 text-rose-600" /></Button></li>)}</ul>
      </div>
    </ModalShell>
  </div>;
}
