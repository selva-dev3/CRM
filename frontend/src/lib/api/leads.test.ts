import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchLeadsApi } from './leads';

const lead = {
  id: 'lead-1',
  title: 'Enterprise renewal',
  company: 'Acme',
  contact_name: 'Jane Doe',
  email: 'jane@acme.test',
  status: 'New',
  source: 'Website',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchLeadsApi', () => {
  it('returns leads with the authoritative total-count metadata', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'X-Total-Count': '31' }),
      json: vi.fn().mockResolvedValue([lead]),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchLeadsApi({ page: 2, limit: 15, search: 'Acme', status: 'New' })).resolves.toEqual({
      items: [lead],
      total: 31,
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/leads?page=2&limit=15&search=Acme&status=New');
  });

  it('rejects responses that omit pagination metadata', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue([lead]),
    }));

    await expect(fetchLeadsApi()).rejects.toThrow('missing valid pagination metadata');
  });
});
