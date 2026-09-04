import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchCompaniesApi, fetchCompaniesPageApi } from './companies';
import {
  fetchContactsApi,
  fetchContactsPageApi,
  fetchStarredContactsApi,
} from './contacts';

afterEach(() => {
  vi.unstubAllGlobals();
});

function response(status: number, data: unknown, total?: string) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(total === undefined ? {} : { 'X-Total-Count': total }),
    json: vi.fn().mockResolvedValue(data),
  };
}

describe('company and contact list pagination', () => {
  it.each([
    [fetchCompaniesPageApi, '/companies'],
    [fetchContactsPageApi, '/contacts'],
  ] as const)('returns server pagination metadata', async (request, path) => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, [{ id: 'record-1' }], '37'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(request(2, 15, 'Acme')).resolves.toEqual({
      items: [{ id: 'record-1' }],
      total: 37,
    });
    expect(fetchMock.mock.calls[0][0]).toContain(`${path}?page=2&limit=15&search=Acme`);
  });

  it.each([fetchCompaniesApi, fetchContactsApi])(
    'propagates list API errors instead of returning an empty result',
    async (request) => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(response(500, { message: 'List unavailable' })),
      );

      await expect(request()).rejects.toThrow('List unavailable');
    },
  );

  it('propagates starred-contact API errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response(500, { message: 'Starred contacts unavailable' })),
    );

    await expect(fetchStarredContactsApi()).rejects.toThrow(
      'Starred contacts unavailable',
    );
  });

  it.each([fetchCompaniesPageApi, fetchContactsPageApi])(
    'rejects missing pagination metadata',
    async (request) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(200, [])));

      await expect(request()).rejects.toThrow('pagination metadata');
    },
  );
});
