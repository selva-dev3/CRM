'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { apiClient } from '@/lib/api/client';
import { usePlatformOrganizationsQuery, type OrganizationItem } from '@/lib/api/organizations';
import { setOrganizationContext } from '@/lib/organization-context';

export function PlatformOrganizations() {
  const [page, setPage] = useState(1);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { data: organizations = [], isPending, isError, refetch } = usePlatformOrganizationsQuery(page);

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
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {isPending ? <p role="status">Loading organizations…</p> : isError ? (
        <div role="alert" className="space-y-2">
          <p>Unable to load organizations.</p>
          <Button variant="outline" onClick={() => void refetch()}>Try again</Button>
        </div>
      ) : organizations.length === 0 ? <p>No organizations found.</p> : (
        <Table>
          <TableHeader><TableRow><TableHead>Organization</TableHead><TableHead>Status</TableHead><TableHead>Members</TableHead><TableHead>Action</TableHead></TableRow></TableHeader>
          <TableBody>
            {organizations.map((organization) => (
              <TableRow key={organization.id}>
                <TableCell className="font-medium">{organization.name}</TableCell>
                <TableCell>{organization.status}</TableCell>
                <TableCell>{organization.members_count ?? 0}</TableCell>
                <TableCell><Button
                  variant="outline"
                  disabled={opening !== null || organization.status !== 'active'}
                  aria-label={`Open ${organization.name}`}
                  onClick={() => void openOrganization(organization)}
                >{opening === organization.id ? 'Opening…' : 'Open organization'}</Button></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <div className="flex items-center gap-3">
        <Button variant="outline" disabled={page === 1 || opening !== null || isPending} onClick={() => setPage(page - 1)}>Previous</Button>
        <span className="text-sm">Page {page}</span>
        <Button variant="outline" disabled={organizations.length < 20 || opening !== null || isPending || isError} onClick={() => setPage(page + 1)}>Next</Button>
      </div>
    </section>
  );
}
