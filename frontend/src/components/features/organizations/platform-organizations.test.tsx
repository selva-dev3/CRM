import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  query: vi.fn(), get: vi.fn(), cancel: vi.fn(), clear: vi.fn(), select: vi.fn(),
  create: vi.fn(), remove: vi.fn(), auth: vi.fn(),
}));
vi.mock('@/providers/auth-provider', () => ({ useAuth: mocks.auth, useOptionalAuth: mocks.auth }));
vi.mock('@/lib/api/organizations', () => ({
  usePlatformOrganizationsQuery: mocks.query,
  useCreateOrganizationMutation: () => ({ mutateAsync: mocks.create, isPending: false }),
  useDeleteOrganizationMutation: () => ({ mutateAsync: mocks.remove, isPending: false }),
  useOrganizationDeletionQuery: () => ({ data: undefined }),
  useRetryOrganizationCleanupMutation: () => ({ isPending: false }),
}));
vi.mock('@/lib/api/client', async (importOriginal) => ({ ...await importOriginal<typeof import('@/lib/api/client')>(), apiClient: { get: mocks.get } }));
vi.mock('@/lib/organization-context', () => ({ setOrganizationContext: mocks.select, getLastOrganizationDeletion: () => null }));
vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ cancelQueries: mocks.cancel, clear: mocks.clear }),
}));

import { PlatformOrganizations } from './platform-organizations';

describe('platform organization selection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.auth.mockReturnValue({ user: { is_platform_admin: true } });
    mocks.query.mockReturnValue({ data: [], isPending: false, isError: false, refetch: vi.fn() });
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('handles loading, errors, and empty organizations', () => {
    mocks.query.mockReturnValue({ isPending: true });
    const view = render(<PlatformOrganizations />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading organizations');
    const refetch = vi.fn();
    mocks.query.mockReturnValue({ isError: true, refetch });
    view.rerender(<PlatformOrganizations />);
    fireEvent.click(screen.getByText('Try again'));
    expect(refetch).toHaveBeenCalledOnce();
    mocks.query.mockReturnValue({ data: [] });
    view.rerender(<PlatformOrganizations />);
    expect(screen.getByText('No organizations found.')).toBeInTheDocument();
  });

  it('validates access, cancels old requests and clears caches before switching', async () => {
    const assign = vi.fn();
    vi.stubGlobal('window', { location: { assign } });
    mocks.query.mockReturnValue({ data: [{ id: 'org-b', name: 'B', status: 'active' }] });
    mocks.get.mockResolvedValue({ id: 'org-b', status: 'active' });
    mocks.cancel.mockResolvedValue(undefined);
    render(<PlatformOrganizations />);
    fireEvent.click(screen.getByRole('button', { name: 'Open B' }));
    await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/organization/org-b'));
    expect(mocks.get).toHaveBeenCalledWith('/organizations/org-b');
    expect(mocks.cancel).toHaveBeenCalledOnce();
    expect(mocks.clear).toHaveBeenCalledOnce();
    expect(mocks.select).toHaveBeenCalledWith('org-b');
    expect(mocks.clear.mock.invocationCallOrder[0]).toBeLessThan(mocks.select.mock.invocationCallOrder[0]);
  });

  it('keeps the current context when access validation fails', async () => {
    mocks.query.mockReturnValue({ data: [{ id: 'org-b', name: 'B', status: 'active' }] });
    mocks.get.mockRejectedValue(new Error('Access denied'));
    render(<PlatformOrganizations />);
    fireEvent.click(screen.getByRole('button', { name: 'Open B' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Access denied');
    expect(mocks.select).not.toHaveBeenCalled();
    expect(mocks.clear).not.toHaveBeenCalled();
  });

  it('hides platform mutations from tenant users', () => {
    mocks.auth.mockReturnValue({ user: { is_platform_admin: false } });
    mocks.query.mockReturnValue({ data: [{ id: 'a', name: 'A', status: 'active' }] });
    render(<PlatformOrganizations />);
    expect(screen.queryByRole('button', { name: '+ Create Organization' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete A' })).not.toBeInTheDocument();
  });

  it('requires deletion confirmation and supports cancel', async () => {
    mocks.query.mockReturnValue({ data: [{ id: 'a', name: 'A', status: 'active' }], refetch: vi.fn() });
    mocks.remove.mockResolvedValue({ operation_id: 'op', cleanup_status: 'complete' });
    render(<PlatformOrganizations />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete A' }));
    expect(mocks.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(mocks.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Delete A' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete Organization' }));
    await vi.waitFor(() => expect(mocks.remove).toHaveBeenCalledWith('a'));
  });

  it('validates the create form and provisions name-only organizations', async () => {
    mocks.create.mockResolvedValue({ organization: { id: 'new', name: 'New' }, invitation: null });
    render(<PlatformOrganizations />);
    fireEvent.click(screen.getByRole('button', { name: '+ Create Organization' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Organization' }));
    expect(await screen.findByText('Organization name is required')).toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Organization Name'), { target: { value: ' New ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Organization' }));
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ name: 'New' }));
  });
});
