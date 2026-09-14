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
  it('returns server pagination metadata for companies', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, [{ id: 'record-1' }], '37'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchCompaniesPageApi(2, 15, 'Acme')).resolves.toEqual({
      items: [{ id: 'record-1' }],
      total: 37,
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/companies?page=2&limit=15&search=Acme');
  });

  it('returns server pagination metadata for contacts with filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, [{ id: 'record-1' }], '37'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchContactsPageApi({
      page: 2,
      limit: 15,
      search: 'Acme',
      companyId: 'company-1',
      ownerId: 'owner-1',
      isStarred: true,
    })).resolves.toEqual({
      items: [{ id: 'record-1' }],
      total: 37,
    });
    expect(fetchMock.mock.calls[0][0]).toContain(
      '/contacts?page=2&limit=15&search=Acme&company_id=company-1&owner_id=owner-1&is_starred=true',
    );
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

  it('rejects missing pagination metadata for companies', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(200, [])));
    await expect(fetchCompaniesPageApi()).rejects.toThrow('pagination metadata');
  });

  it('rejects missing pagination metadata for contacts', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(200, [])));

      await expect(fetchContactsPageApi()).rejects.toThrow('pagination metadata');
  });
});
