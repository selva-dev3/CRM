import { beforeEach, describe, expect, it, vi } from 'vitest';

const getWithMetadata = vi.fn();

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    getWithMetadata: (...args: unknown[]) => getWithMetadata(...args),
  },
}));

import { fetchActivitiesPageApi } from './activities';

describe('activities API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getWithMetadata.mockResolvedValue({
      data: [],
      headers: new Headers({ 'X-Total-Count': '0' }),
    });
  });

  it('sends pagination and active filters to the activity feed endpoint', async () => {
    await fetchActivitiesPageApi({
      page: 2,
      limit: 20,
      module: 'calls',
      search: 'discovery',
    });

    expect(getWithMetadata).toHaveBeenCalledWith(
      '/activities?page=2&limit=20&module=calls&search=discovery',
    );
  });

  it('returns the server total with activity rows', async () => {
    getWithMetadata.mockResolvedValue({
      data: [{ id: 'calls:call-1' }],
      headers: new Headers({ 'X-Total-Count': '14' }),
    });

    await expect(fetchActivitiesPageApi()).resolves.toEqual({
      items: [{ id: 'calls:call-1' }],
      total: 14,
    });
  });
});
