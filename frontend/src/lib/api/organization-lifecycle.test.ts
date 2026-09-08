import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  mutation: vi.fn(), query: vi.fn(), post: vi.fn(), remove: vi.fn(), cancel: vi.fn(),
  clear: vi.fn(), invalidate: vi.fn(), selected: vi.fn(), select: vi.fn(),
  broadcast: vi.fn(), remember: vi.fn(), assign: vi.fn(),
  persist: vi.fn(), notify: vi.fn(),
}));
vi.mock('@tanstack/react-query', () => ({
  useMutation: mocks.mutation, useQuery: mocks.query,
  useQueryClient: () => ({ cancelQueries: mocks.cancel, clear: mocks.clear, removeQueries: mocks.remove, invalidateQueries: mocks.invalidate }),
}));
vi.mock('@/lib/api/client', () => ({ apiClient: { post: mocks.post } }));
vi.mock('@/lib/auth-session', () => ({ persistSessionUser: mocks.persist }));
vi.mock('@/hooks/use-has-permission', () => ({ notifyAuthUserChanged: mocks.notify }));
vi.mock('@/lib/organization-context', () => ({
  getOrganizationContext: mocks.selected, setOrganizationContext: mocks.select,
  broadcastOrganizationDeleted: mocks.broadcast, rememberOrganizationDeletion: mocks.remember,
}));
import { useAcceptInvitationMutation, useCreateOrganizationMutation, useDeleteOrganizationMutation, useOrganizationDeletionQuery } from './organizations';

describe('platform organization cache lifecycle', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal('window', { location: { assign: mocks.assign } });
  });
  it('refreshes the platform list after provisioning', async () => {
    useCreateOrganizationMutation();
    const options = mocks.mutation.mock.calls[0][0];
    await options.mutationFn({ name: 'New organization' });
    await options.onSuccess();
    expect(mocks.post).toHaveBeenCalledWith('/organizations', { name: 'New organization' });
    expect(mocks.invalidate).toHaveBeenCalledWith({ queryKey: ['platform-organizations'] });
    expect(options.retry).toBe(false);
  });
  it('clears stale tenant state before installing an accepted invitation session', async () => {
    const user = {
      id: 'user-1', name: 'Invitee', email: 'invitee@crm.com', role: 'Admin',
      organization_id: 'new-organization', permissions: ['users:read'], is_platform_admin: false,
    };
    useAcceptInvitationMutation();
    const options = mocks.mutation.mock.calls[0][0];

    await options.onSuccess({ token_type: 'bearer', user, message: 'Accepted' });

    expect(mocks.select).toHaveBeenCalledWith(null);
    expect(mocks.clear).toHaveBeenCalled();
    expect(mocks.persist).toHaveBeenCalledWith(user, { remember: true });
    expect(mocks.notify).toHaveBeenCalled();
    expect(mocks.clear.mock.invocationCallOrder[0]).toBeLessThan(mocks.persist.mock.invocationCallOrder[0]);
  });
  it('clears selected tenant context and all caches before returning to the list', async () => {
    mocks.selected.mockReturnValue('deleted');
    useDeleteOrganizationMutation();
    await mocks.mutation.mock.calls[0][0].onSuccess({ operation_id: 'operation' }, 'deleted');
    expect(mocks.remember).toHaveBeenCalledWith('operation');
    expect(mocks.cancel).toHaveBeenCalled();
    expect(mocks.clear).toHaveBeenCalled();
    expect(mocks.select).toHaveBeenCalledWith(null);
    expect(mocks.broadcast).toHaveBeenCalledWith('deleted');
    expect(mocks.assign).toHaveBeenCalledWith('/organization');
    expect(mocks.clear.mock.invocationCallOrder[0]).toBeLessThan(mocks.assign.mock.invocationCallOrder[0]);
  });
  it('retains a different valid selection while removing stale tenant queries', async () => {
    mocks.selected.mockReturnValue('survivor');
    useDeleteOrganizationMutation();
    await mocks.mutation.mock.calls[0][0].onSuccess({ operation_id: 'operation' }, 'deleted');
    expect(mocks.select).not.toHaveBeenCalled();
    expect(mocks.assign).not.toHaveBeenCalled();
    const { predicate } = mocks.remove.mock.calls[0][0];
    expect(predicate({ queryKey: ['users'] })).toBe(true);
    expect(predicate({ queryKey: ['dashboard'] })).toBe(true);
    expect(predicate({ queryKey: ['organization', 'deleted'] })).toBe(true);
    expect(predicate({ queryKey: ['platform-organizations', 1, 20] })).toBe(false);
    expect(mocks.invalidate).toHaveBeenCalledWith({ queryKey: ['platform-organizations'] });
  });
  it('bounds cleanup polling and stops on completion or failure', () => {
    useOrganizationDeletionQuery('operation');
    const { refetchInterval } = mocks.query.mock.calls[0][0];
    expect(refetchInterval({ state: { data: { cleanup_status: 'pending' }, dataUpdateCount: 2 } })).toBe(5000);
    expect(refetchInterval({ state: { data: { cleanup_status: 'pending' }, dataUpdateCount: 60 } })).toBe(false);
    expect(refetchInterval({ state: { data: { cleanup_status: 'failed' }, dataUpdateCount: 2 } })).toBe(false);
    expect(refetchInterval({ state: { data: { cleanup_status: 'complete' }, dataUpdateCount: 2 } })).toBe(false);
  });
});
