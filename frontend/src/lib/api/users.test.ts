import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchUserActivitiesApi,
  bulkDeactivateUsersApi,
  fetchUserPerformanceApi,
  fetchUserPermissionsApi,
  fetchUserQuotaApi,
  fetchUserTeamsApi,
} from './users';

const failedResponse = {
  ok: false,
  status: 500,
  json: vi.fn().mockResolvedValue({ message: 'Request failed' }),
};

describe('user detail API requests', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    ['quota', fetchUserQuotaApi],
    ['performance', fetchUserPerformanceApi],
    ['permissions', fetchUserPermissionsApi],
    ['activities', fetchUserActivitiesApi],
    ['teams', fetchUserTeamsApi],
  ])('propagates a failed %s request instead of returning demo data', async (_name, request) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failedResponse));

    await expect(request('user-1')).rejects.toThrow('Request failed');
  });

  it('preserves valid zero and empty values returned by the API', async () => {
    const responses = [
      { user_id: 'user-1', target_amount: null, achieved_amount: 0 },
      { user_id: 'user-1', win_rate: 0, avg_deal_size: 0, calls_made: 0 },
      { user_id: 'user-1', permissions: [] },
      [],
      [],
    ];
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers(),
          json: vi.fn().mockResolvedValue(responses.shift()),
        }),
      ),
    );

    await expect(fetchUserQuotaApi('user-1')).resolves.toMatchObject({
      target_amount: null,
      achieved_amount: 0,
    });
    await expect(fetchUserPerformanceApi('user-1')).resolves.toMatchObject({
      win_rate: 0,
      avg_deal_size: 0,
      calls_made: 0,
    });
    await expect(fetchUserPermissionsApi('user-1')).resolves.toMatchObject({ permissions: [] });
    await expect(fetchUserActivitiesApi('user-1')).resolves.toEqual([]);
    await expect(fetchUserTeamsApi('user-1')).resolves.toEqual([]);
  });

  it('uses one backend operation for bulk deactivation', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({ affected_count: 2, message: 'Users deactivated' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await bulkDeactivateUsersApi(['user-1', 'user-2']);

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.method).toBe('POST');
    expect(JSON.parse(String(request.body))).toEqual({ ids: ['user-1', 'user-2'] });
  });
});
