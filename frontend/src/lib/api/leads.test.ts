import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  deleteLeadCallApi,
  fetchLeadsApi,
  logLeadCallApi,
  sendLeadEmailApi,
  updateLeadCallApi,
} from './leads';

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
  vi.restoreAllMocks();
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

describe('sendLeadEmailApi', () => {
  it('sends the idempotency key with the Lead email request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({
        id: 'email-1',
        from_email: 'rep@crm.test',
        to: ['jane@acme.test'],
        subject: 'Hello',
        status: 'Pending',
        sent_at: null,
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await sendLeadEmailApi(
      'lead-1',
      { to: ['jane@acme.test'], subject: 'Hello', body: 'Hi Jane' },
      'email-key-1',
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/leads/lead-1/emails/send'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Idempotency-Key': 'email-key-1' }),
      }),
    );
  });

  it('generates an idempotency key when a caller does not supply one', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({ id: 'email-1', status: 'Pending' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('11111111-1111-4111-8111-111111111111');

    await sendLeadEmailApi('lead-1', {
      to: ['jane@acme.test'],
      subject: 'Hello',
      body: 'Follow up',
    });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get('Idempotency-Key')).toBe(
      '11111111-1111-4111-8111-111111111111',
    );
  });
});

describe('lead call APIs', () => {
  it('sends the create idempotency key and uses generic update/delete routes', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({ id: 'call-1', status: 'success' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await logLeadCallApi(
      'lead-1',
      { call_type: 'Outbound', disposition: 'Completed', duration_seconds: 0 },
      'call-key-1',
    );
    await updateLeadCallApi('call-1', { notes: 'Updated' });
    await deleteLeadCallApi('call-1');

    expect(fetchMock.mock.calls[0][0]).toContain('/leads/lead-1/calls');
    expect(new Headers((fetchMock.mock.calls[0][1] as RequestInit).headers).get('Idempotency-Key')).toBe('call-key-1');
    expect(fetchMock.mock.calls[1][0]).toContain('/calls/call-1');
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: 'PUT' }));
    expect(fetchMock.mock.calls[2][0]).toContain('/calls/call-1');
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ method: 'DELETE' }));
  });
});
