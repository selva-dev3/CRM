import { afterEach, describe, expect, it, vi } from 'vitest';

import { createDealApi, fetchDealCustomFieldsApi } from './deals';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('deal custom field API', () => {
  it('loads tenant-scoped Deal field definitions', async () => {
    const fields = [
      { field_name: 'decision_maker', field_type: 'text', label: 'Decision Maker', options: [] },
    ];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue(fields),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchDealCustomFieldsApi()).resolves.toEqual(fields);
    expect(fetchMock.mock.calls[0][0]).toContain('/deals/custom-fields');
  });

  it('includes custom values in the create payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({ id: 'deal-1' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await createDealApi({
      title: 'Enterprise Deal',
      amount: 1000,
      stage: 'Prospecting',
      custom_fields: { decision_maker: 'CTO' },
    });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      custom_fields: { decision_maker: 'CTO' },
    });
  });
});
