import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchPaginated } from './pagination';

afterEach(() => {
  vi.unstubAllGlobals();
});

function response(data: unknown, total?: string) {
  return {
    ok: true,
    status: 200,
    headers: new Headers(total === undefined ? {} : { 'X-Total-Count': total }),
    json: vi.fn().mockResolvedValue(data),
  };
}

describe('fetchPaginated', () => {
  it('returns the response items and authoritative total', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response([{ id: 'record-1' }], '42')),
    );

    await expect(fetchPaginated<{ id: string }>('/records?page=2')).resolves.toEqual({
      items: [{ id: 'record-1' }],
      total: 42,
    });
  });

  it.each([undefined, '', '-1', '1.5', 'not-a-number'])(
    'rejects invalid total metadata: %s',
    async (total) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([], total)));

      await expect(fetchPaginated('/records')).rejects.toThrow(
        'Missing or invalid X-Total-Count header',
      );
    },
  );
});
