import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  query: vi.fn(), get: vi.fn(), cancel: vi.fn(), clear: vi.fn(), select: vi.fn(),
}));
vi.mock('@/lib/api/organizations', () => ({ usePlatformOrganizationsQuery: mocks.query }));
vi.mock('@/lib/api/client', () => ({ apiClient: { get: mocks.get } }));
vi.mock('@/lib/organization-context', () => ({ setOrganizationContext: mocks.select }));
vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ cancelQueries: mocks.cancel, clear: mocks.clear }),
}));

import { PlatformOrganizations } from './platform-organizations';

describe('platform organization selection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.query.mockReturnValue({ data: [], isPending: false, isError: false });
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
});
