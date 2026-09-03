import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchAssignableRolesApi } from './roles';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchAssignableRolesApi', () => {
  it('uses the backend assignable-role endpoint and preserves search', async () => {
    const roles = [{ id: 'role-1', name: 'Sales Manager', is_system_role: true }];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue(roles),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchAssignableRolesApi('Sales Manager')).resolves.toEqual(roles);
    expect(fetchMock.mock.calls[0][0]).toContain(
      '/roles/assignable?search=Sales%20Manager',
    );
  });
});
