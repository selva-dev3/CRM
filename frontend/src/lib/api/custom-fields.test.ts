import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchEntityCustomFieldsApi } from './custom-fields';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('entity custom field API', () => {
  it.each([
    ['Lead', '/leads/custom-fields'],
    ['Contact', '/contacts/custom-fields'],
    ['Company', '/companies/custom-fields'],
    ['Deal', '/deals/custom-fields'],
  ] as const)('loads %s definitions from its permission-scoped endpoint', async (entity, path) => {
    const fields = [
      { field_name: 'priority', field_type: 'text', label: 'Priority', options: [] },
    ];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue(fields),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchEntityCustomFieldsApi(entity)).resolves.toEqual(fields);
    expect(fetchMock.mock.calls[0][0]).toContain(path);
  });

  it.each([400, 401, 422, 500])('propagates an HTTP %s response', async (status) => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({ message: 'Custom fields unavailable' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchEntityCustomFieldsApi('Lead')).rejects.toThrow(
      'Custom fields unavailable',
    );
  });
});
