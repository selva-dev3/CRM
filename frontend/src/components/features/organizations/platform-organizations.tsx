'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Loader2, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { apiClient } from '@/lib/api/client';
import { usePlatformOrganizationsQuery, useDeleteOrganizationMutation, useOrganizationDeletionQuery, useRetryOrganizationCleanupMutation, type OrganizationItem } from '@/lib/api/organizations';
import { getLastOrganizationDeletion, setOrganizationContext } from '@/lib/organization-context';
import { useAuth } from '@/providers/auth-provider';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { CreateOrganizationDialog } from './create-organization-dialog';

const organizationColumns: readonly DataTableColumn<OrganizationItem>[] = [
  { id: 'organization', header: 'Organization', cell: (organization) => organization.name },
  { id: 'status', header: 'Status', cell: (organization) => organization.status },
  { id: 'members', header: 'Members', cell: (organization) => organization.members_count ?? 0 },
];

export function PlatformOrganizations() {
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<OrganizationItem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [operationId, setOperationId] = useState<string | null>(getLastOrganizationDeletion);
  const deleteMutation = useDeleteOrganizationMutation();
  const cleanupQuery = useOrganizationDeletionQuery(operationId);
  const retryCleanup = useRetryOrganizationCleanupMutation();
  const [page, setPage] = useState(1);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { data: organizationsPage, isPending, isError, refetch } = usePlatformOrganizationsQuery(page);
  const organizations = organizationsPage?.items ?? [];
  const totalOrganizations = organizationsPage?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalOrganizations / 20));
  const busy = opening !== null || deleteMutation.isPending;

  const confirmDelete = async () => {
    if (!deleting || deleteMutation.isPending) return;
    setError(null);
    try {
      const result = await deleteMutation.mutateAsync(deleting.id);
      setOperationId(result.operation_id);
      setNotice(`Organization "${deleting.name}" deleted. File cleanup: ${result.cleanup_status}.`);
      setDeleting(null);
      if (organizations.length === 1 && page > 1) setPage(page - 1);
      else await refetch();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to delete organization.');
    }
  };

  const openOrganization = async (organization: OrganizationItem) => {
    setOpening(organization.id);
    setError(null);
    try {
      // Validate access before changing selection. Every subsequent request is
      // independently authorized using the same session and selected context.
      const current = await apiClient.get<OrganizationItem>(`/organizations/${organization.id}`);
      if (current.status !== 'active') throw new Error('This organization is inactive.');
      await queryClient.cancelQueries();
      queryClient.clear();
      setOrganizationContext(organization.id);
      // A fresh document discards all tenant caches, forms, and in-flight UI state.
      // HttpOnly authentication cookies are retained: this is the same login.
      window.location.assign(`/organization/${encodeURIComponent(organization.id)}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to open the organization.');
      setOpening(null);
    }
  };

  return (
    <section className="space-y-5 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-semibold">Organizations</h1>
        <p className="text-sm text-muted-foreground">Select an organization to manage its users, roles, and settings.</p>
        {user?.is_platform_admin && <Button className="mt-3" disabled={busy} onClick={() => setCreating(true)}>+ Create Organization</Button>}
      </div>
      {notice && <p role="status">{notice}</p>}
      {operationId && <div className="space-y-2 text-sm">
        {cleanupQuery.isError ? <p role="alert">Unable to load file cleanup status.</p> : cleanupQuery.data && <p>File cleanup: {cleanupQuery.data.cleanup_status}. {cleanupQuery.data.pending_files} pending, {cleanupQuery.data.failed_files} failed.</p>}
        <Button variant="outline" onClick={() => void cleanupQuery.refetch()}>Refresh cleanup status</Button>
        {cleanupQuery.data?.cleanup_status === 'failed' && <Button disabled={retryCleanup.isPending} onClick={() => retryCleanup.mutate(operationId)}>Retry file cleanup</Button>}
        {retryCleanup.isError && <p role="alert">Unable to retry file cleanup.</p>}
      </div>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {isPending ? <p role="status">Loading organizations…</p> : isError ? (
        <div role="alert" className="space-y-2">
          <p>Unable to load organizations.</p>
          <Button variant="outline" onClick={() => void refetch()}>Try again</Button>
        </div>
      ) : (
        <DataTable
          columns={organizationColumns}
          data={organizations}
          getRowKey={(organization) => organization.id}
          emptyTitle="No organizations found."
          emptyDescription="Create an organization to begin managing a tenant."
          tableClassName="min-w-[640px]"
          actionVariant="inline"
          actionColumnClassName="w-[260px]"
          actions={(organization) => [
            {
              id: 'open',
              label: opening === organization.id ? 'Opening…' : 'Open organization',
              ariaLabel: `Open ${organization.name}`,
              icon: opening === organization.id ? <Loader2 className="size-3.5 animate-spin" /> : <ExternalLink className="size-3.5" />,
              disabled: busy || organization.status !== 'active',
              isLoading: opening === organization.id,
              onClick: () => void openOrganization(organization),
            },
            ...(user?.is_platform_admin ? [{
              id: 'delete',
              label: 'Delete',
              ariaLabel: `Delete ${organization.name}`,
              icon: <Trash2 className="size-3.5" />,
              variant: 'destructive' as const,
              disabled: busy,
              onClick: () => { setError(null); setDeleting(organization); },
            }] : []),
          ]}
        />
      )}
      <div className="flex items-center gap-3">
        <Button variant="outline" disabled={page === 1 || opening !== null || isPending} onClick={() => setPage(page - 1)}>Previous</Button>
        <span className="text-sm">Page {page} of {pageCount} · {totalOrganizations} total</span>
        <Button variant="outline" disabled={page >= pageCount || opening !== null || isPending || isError} onClick={() => setPage(page + 1)}>Next</Button>
      </div>
      {creating && user?.is_platform_admin && <CreateOrganizationDialog onClose={() => setCreating(false)} onCreated={(result) => {
        setCreating(false);
        setNotice(`Organization "${result.organization.name}" created.${result.invitation?.delivery_status === 'failed' ? ' Invitation email failed; open the organization to resend it.' : ''}`);
        setPage(1);
        void refetch();
      }} />}
      {deleting && <ConfirmModal isOpen={Boolean(user?.is_platform_admin)} onClose={() => { if (!deleteMutation.isPending) setDeleting(null); }} onConfirm={() => void confirmDelete()}
        title="Delete Organization?" confirmText="Delete Organization" isLoading={deleteMutation.isPending}
        description={`Organization: ${deleting?.name ?? ''}. This permanently removes the organization, its tenant accounts, and associated database records. Stored files are queued for deletion; existing file links may work until cleanup completes. Audit and recovery records are retained.`}
        message={error ? <p role="alert" className="text-destructive">{error}</p> : undefined} />}
    </section>
  );
}
