import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import IntegrationsPage from './page';

const state = vi.hoisted(() => ({
  permissions: new Set<string>(),
  platform: false,
  keys: [] as { id: string; is_active: boolean; scopes: string[] }[],
  fetchKeys: vi.fn(),
  can: (permission?: string): boolean => !permission || state.permissions.has(permission),
}));
vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: state.can }),
}));
vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({ user: { is_platform_admin: state.platform } }),
}));
vi.mock('@/lib/api/integrations', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/api/integrations')>(),
  fetchApiKeysApi: () => { state.fetchKeys(); return Promise.resolve(state.keys); },
}));

describe('API key action authorization', () => {
  beforeEach(() => {
    state.permissions = new Set(['api_keys:read', 'api_keys:create']);
    state.platform = false;
    state.keys = [];
    state.fetchKeys.mockClear();
  });

  it('allows initial creation without revocation authority', async () => {
    render(<IntegrationsPage />);
    await waitFor(() => expect(state.fetchKeys).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'Create Key' })).toBeInTheDocument();
  });

  it('requires revocation permission to regenerate an existing key', async () => {
    state.keys = [{ id: 'key-1', is_active: true, scopes: ['api:read'] }];
    render(<IntegrationsPage />);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Create Key' })).not.toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Regenerate Key' })).not.toBeInTheDocument();
  });

  it('allows regeneration with creation and revocation permissions', async () => {
    state.permissions.add('api_keys:revoke');
    state.keys = [{ id: 'key-1', is_active: true, scopes: ['api:read'] }];
    render(<IntegrationsPage />);
    expect(await screen.findByRole('button', { name: 'Regenerate Key' })).toBeInTheDocument();
  });

  it('does not offer platform-owned key creation', async () => {
    state.platform = true;
    render(<IntegrationsPage />);
    await waitFor(() => expect(state.fetchKeys).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Create Key' })).not.toBeInTheDocument();
    expect(screen.getByText('API keys must be created by an organization user.')).toBeInTheDocument();
  });
});
