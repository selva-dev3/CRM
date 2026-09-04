import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  fetchAuditLogsApi,
  fetchBackupsApi,
  fetchSlaPoliciesApi,
  fetchSystemSettingsApi,
  fetchWebhooksApi,
} from './settings';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('settings API failures', () => {
  it.each([
    fetchSystemSettingsApi,
    fetchAuditLogsApi,
    fetchWebhooksApi,
    fetchSlaPoliciesApi,
    fetchBackupsApi,
  ])('propagates the backend error instead of returning fabricated data', async (request) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers(),
        json: vi.fn().mockResolvedValue({ message: 'Settings unavailable' }),
      }),
    );

    await expect(request()).rejects.toThrow('Settings unavailable');
  });
});
