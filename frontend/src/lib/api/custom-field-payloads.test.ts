import { afterEach, describe, expect, it, vi } from 'vitest';

import { createCompanyApi } from './companies';
import { createContactApi } from './contacts';
import { createLeadApi } from './leads';

afterEach(() => {
  vi.unstubAllGlobals();
});

function successfulFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 201,
    headers: new Headers(),
    json: vi.fn().mockResolvedValue({ id: 'record-1' }),
  });
}

describe('custom field create payloads', () => {
  it.each([
    [
      () =>
        createLeadApi({
          title: 'Acme Opportunity',
          company: 'Acme',
          contact_name: 'Jane Doe',
          email: 'jane@acme.test',
          custom_fields: { territory: 'South' },
        }),
      { territory: 'South' },
    ],
    [
      () =>
        createContactApi({
          name: 'Jane Doe',
          email: 'jane@acme.test',
          custom_fields: { preferred_channel: 'Email' },
        }),
      { preferred_channel: 'Email' },
    ],
    [
      () =>
        createCompanyApi({
          name: 'Acme',
          custom_fields: { account_tier: 'Gold' },
        }),
      { account_tier: 'Gold' },
    ],
  ])('sends custom values without dropping them', async (request, expectedCustomFields) => {
    const fetchMock = successfulFetch();
    vi.stubGlobal('fetch', fetchMock);

    await request();

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(options.body))).toMatchObject({
      custom_fields: expectedCustomFields,
    });
  });
});
