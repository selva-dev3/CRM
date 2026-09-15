import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setOrganizationContext } from '@/lib/organization-context';
import {
  API_REQUEST_TIMEOUT_MS,
  apiClient,
  BASE_URL,
  captureAuthSessionGeneration,
  clearSessionToken,
  invalidateAuthSession,
  isAuthSessionGenerationCurrent,
  markAuthSessionActive,
  openApiStream,
  resolveApiBaseUrl,
} from './client';
import { AUTH_ACCESS_TOKEN_KEY, getAccessToken } from '@/lib/auth-session';

const ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjIwMDAwMDAwMDB9.signature';
const REFRESHED_ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjIwMDAwMDAwMDF9.signature';

describe('apiClient cookie authentication', () => {
  beforeEach(() => {
    markAuthSessionActive();
    localStorage.setItem(AUTH_ACCESS_TOKEN_KEY, ACCESS_TOKEN);
  });

  it('uses the same cookie session while changing organization context', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200, headers: new Headers(), json: async () => ([]),
    });
    vi.stubGlobal('fetch', fetchMock);
    for (const organization of ['org-a', 'org-b']) {
      setOrganizationContext(organization);
      await apiClient.get('/roles');
      const options = fetchMock.mock.lastCall?.[1] as RequestInit;
      expect(new Headers(options.headers).get('X-Organization-ID')).toBe(organization);
      expect(options.credentials).toBe('include');
    }
    await apiClient.get('/organizations/all');
    expect(new Headers(fetchMock.mock.lastCall?.[1].headers).has('X-Organization-ID')).toBe(false);
    await apiClient.get('/auth/me');
    expect(new Headers(fetchMock.mock.lastCall?.[1].headers).get('X-Organization-ID')).toBe('org-b');
    setOrganizationContext(null);
    await apiClient.get('/roles');
    expect(new Headers(fetchMock.mock.lastCall?.[1].headers).has('X-Organization-ID')).toBe(false);
  });

  it('keeps platform mutations independent of a stale selected organization', async () => {
    setOrganizationContext('deleted-organization');
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
    await apiClient.post('/organizations', { name: 'New' });
    await apiClient.delete('/organizations/deleted-organization');
    for (const [, options] of fetchMock.mock.calls) {
      expect(new Headers(options.headers).has('X-Organization-ID')).toBe(false);
      expect(options.credentials).toBe('include');
    }
  });

  it('identifies the request organization when reporting an unavailable context', async () => {
    setOrganizationContext('old-organization');
    const listener = vi.fn();
    window.addEventListener('organization:unavailable', listener);
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => {
      setOrganizationContext('new-organization');
      return { ok: false, status: 403, json: async () => ({ code: 'ORGANIZATION_UNAVAILABLE', message: 'Unavailable' }) };
    }));
    await expect(apiClient.get('/roles')).rejects.toThrow('Unavailable');
    expect(listener.mock.calls[0][0].detail).toBe('old-organization');
    window.removeEventListener('organization:unavailable', listener);
  });

  it('allows a lifecycle request to finish after the default timeout', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation(() => new Promise(resolve => {
      setTimeout(() => resolve({ ok: true, status: 200, headers: new Headers(), json: async () => ({ status: 'success' }) }), 20_000);
    }));
    vi.stubGlobal('fetch', fetchMock);
    try {
      const request = apiClient.delete('/organizations/slow', { timeoutMs: 120_000 });
      await vi.advanceTimersByTimeAsync(20_000);
      await expect(request).resolves.toEqual({ status: 'success' });
      expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not refresh, clear the CRM session, or redirect on invalid public invoice tokens', async () => {
    sessionStorage.setItem('user', 'existing-session');
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ message: 'Invalid invoice link' }) });
    vi.stubGlobal('fetch', fetchMock);
    const unauthorized = vi.fn();
    window.addEventListener('auth:unauthorized', unauthorized);
    await expect(apiClient.post('/public/invoices/view', { token: 'invalid' }, { credentials: 'omit' })).rejects.toThrow('Invalid invoice link');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem('user')).toBe('existing-session');
    expect(unauthorized).not.toHaveBeenCalled();
    window.removeEventListener('auth:unauthorized', unauthorized);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('uses a local backend fallback instead of an external production host', () => {
    expect(BASE_URL).toBe('http://localhost:8000/api/v1');
    expect(BASE_URL).not.toContain('railway.app');
  });

  it('requires an explicit API URL in production', () => {
    expect(() => resolveApiBaseUrl(undefined, 'production')).toThrow(
      'NEXT_PUBLIC_API_URL must be configured for production.',
    );
    expect(resolveApiBaseUrl(' https://api.example.com/v1 ', 'production')).toBe(
      'https://api.example.com/v1',
    );
  });

  it('includes credentials and attaches the canonical Authorization token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.get('/auth/me');

    expect(fetchMock).toHaveBeenCalledOnce();
    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.credentials).toBe('include');
    expect(new Headers(options.headers).get('Authorization')).toBe(`Bearer ${ACCESS_TOKEN}`);
  });

  it('omits CRM cookies and does not refresh authentication for public quote requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401,
      json: vi.fn().mockResolvedValue({ message: 'Invalid quote link' }) });
    vi.stubGlobal('fetch', fetchMock);
    await expect(apiClient.post('/public/quotes/view', { token: 'invalid' }, { credentials: 'omit' }))
      .rejects.toThrow('Invalid quote link');
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][1].credentials).toBe('omit');
  });

  it('removes legacy browser-readable auth data', () => {
    localStorage.setItem('token', 'legacy-token');
    sessionStorage.setItem('token', 'legacy-token');
    localStorage.setItem('user', '{}');

    clearSessionToken();

    expect(localStorage.getItem('token')).toBeNull();
    expect(sessionStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('does not attach the CRM token to public requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.post('/public/quotes/view', { token: 'public-token' }, { credentials: 'omit' });

    expect(new Headers(fetchMock.mock.calls[0][1].headers).has('Authorization')).toBe(false);
  });

  it('removes malformed stored tokens before they reach the API', () => {
    localStorage.setItem(AUTH_ACCESS_TOKEN_KEY, 'not-a-jwt');

    expect(getAccessToken()).toBeNull();
    expect(localStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBeNull();
  });

  it('returns response metadata when requested', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'X-Total-Count': '7' }),
      json: vi.fn().mockResolvedValue([{ id: 'lead-1' }]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await apiClient.getWithMetadata<Array<{ id: string }>>('/leads');

    expect(response.data).toEqual([{ id: 'lead-1' }]);
    expect(response.headers.get('X-Total-Count')).toBe('7');
    expect(response.status).toBe(200);
  });

  it('refreshes once and retries the original request after a 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ access_token: ACCESS_TOKEN }) })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: vi.fn().mockResolvedValue({ id: 'user-1' }),
      });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.get('/auth/me')).resolves.toEqual({ id: 'user-1' });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toBe(`${BASE_URL}/auth/refresh-token`);
    expect(fetchMock.mock.calls[2][0]).toBe(`${BASE_URL}/auth/me`);
  });

  it('replaces the expired token and retries with the refreshed token', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({ access_token: REFRESHED_ACCESS_TOKEN }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: vi.fn().mockResolvedValue({ ok: true }),
      });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.get('/users')).resolves.toEqual({ ok: true });

    expect(localStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe(REFRESHED_ACCESS_TOKEN);
    expect(new Headers(fetchMock.mock.calls[2][1].headers).get('Authorization')).toBe(
      `Bearer ${REFRESHED_ACCESS_TOKEN}`,
    );
  });

  it('does not recursively refresh the refresh endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ message: 'Invalid refresh token' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.post('/auth/refresh-token')).rejects.toThrow(
      'Invalid refresh token',
    );
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('clears local session data when refresh fails on the login page', async () => {
    window.history.replaceState({}, '', '/login');
    localStorage.setItem('user', '{}');
    sessionStorage.setItem('user', '{}');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: vi.fn().mockResolvedValue({ detail: 'Session token missing' }),
      })
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.get('/auth/me')).rejects.toThrow('Session token missing');

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(localStorage.getItem('user')).toBeNull();
    expect(sessionStorage.getItem('user')).toBeNull();
    expect(window.location.pathname).toBe('/login');
  });

  it('shares one refresh request across concurrent 401 responses', async () => {
    let releaseRefresh: (() => void) | undefined;
    const refreshResponse = new Promise<{ ok: boolean; status: number; json: () => Promise<object> }>((resolve) => {
      releaseRefresh = () => resolve({ ok: true, status: 200, json: async () => ({ access_token: ACCESS_TOKEN }) });
    });
    let protectedCalls = 0;
    let refreshCalls = 0;
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh-token')) {
        refreshCalls += 1;
        return refreshResponse;
      }
      protectedCalls += 1;
      if (protectedCalls <= 2) {
        return Promise.resolve({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: vi.fn().mockResolvedValue({ ok: true }),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const requests = [apiClient.get('/users'), apiClient.get('/roles')];
    await vi.waitFor(() => expect(refreshCalls).toBe(1));
    releaseRefresh?.();

    await expect(Promise.all(requests)).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(refreshCalls).toBe(1);
  });

  it('does not retry a request when explicit logout begins during refresh', async () => {
    let releaseRefresh: (() => void) | undefined;
    const refreshResponse = new Promise<{ ok: boolean; status: number; json: () => Promise<object> }>((resolve) => {
      releaseRefresh = () => resolve({ ok: true, status: 200, json: async () => ({ access_token: ACCESS_TOKEN }) });
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) })
      .mockReturnValueOnce(refreshResponse);
    vi.stubGlobal('fetch', fetchMock);

    const request = apiClient.get('/users');
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    invalidateAuthSession();
    releaseRefresh?.();

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not apply a successful response that completes after logout', async () => {
    let releaseRequest: ((response: object) => void) | undefined;
    const pendingResponse = new Promise<object>((resolve) => {
      releaseRequest = resolve;
    });
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pendingResponse));

    const request = apiClient.get('/contacts');
    invalidateAuthSession();
    releaseRequest?.({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue([{ id: 'account-a-contact' }]),
    });

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('does not apply a response body decoded after an account switch', async () => {
    let releaseBody: ((value: object) => void) | undefined;
    const body = new Promise<object>((resolve) => {
      releaseBody = resolve;
    });
    const json = vi.fn().mockReturnValue(body);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json,
    }));

    const request = apiClient.get('/contacts');
    await vi.waitFor(() => expect(json).toHaveBeenCalledOnce());
    invalidateAuthSession();
    markAuthSessionActive();
    releaseBody?.([{ id: 'account-a-contact' }]);

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('does not apply a delayed error body to a replacement session', async () => {
    let releaseBody: ((value: object) => void) | undefined;
    const body = new Promise<object>((resolve) => {
      releaseBody = resolve;
    });
    const json = vi.fn().mockReturnValue(body);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403, json }));
    const unavailable = vi.fn();
    window.addEventListener('organization:unavailable', unavailable);

    const request = apiClient.get('/contacts');
    await vi.waitFor(() => expect(json).toHaveBeenCalledOnce());
    invalidateAuthSession();
    markAuthSessionActive();
    sessionStorage.setItem('user', 'account-b');
    releaseBody?.({ code: 'ORGANIZATION_UNAVAILABLE', message: 'Old account error' });

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
    expect(sessionStorage.getItem('user')).toBe('account-b');
    expect(unavailable).not.toHaveBeenCalled();
    window.removeEventListener('organization:unavailable', unavailable);
  });

  it('stops consuming an authenticated stream after an account switch', async () => {
    let streamController: ReadableStreamDefaultController<Uint8Array> | undefined;
    const source = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller;
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(source, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })));

    const response = await openApiStream('/ai/chat', { prompt: 'Pipeline summary' });
    const bodyRead = response.text();
    const rejection = expect(bodyRead).rejects.toMatchObject({ name: 'AbortError' });
    invalidateAuthSession();
    markAuthSessionActive();

    await rejection;
    expect(() => streamController?.enqueue(new Uint8Array())).toThrow();
  });

  it('does not expose a prefetched stream chunk after an account switch', async () => {
    const source = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: private account-a\n\n'));
        controller.close();
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(source, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })));

    const response = await openApiStream('/ai/chat', { prompt: 'Private pipeline' });
    await Promise.resolve();
    invalidateAuthSession();
    markAuthSessionActive();

    await expect(response.text()).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('continues streaming while the authenticated session is unchanged', async () => {
    const source = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: permitted\n\n'));
        controller.close();
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(source, { status: 200 })));

    const response = await openApiStream('/ai/chat', { prompt: 'Pipeline' });

    await expect(response.text()).resolves.toBe('data: permitted\n\n');
  });

  it('does not refresh or redirect when an account changes before a delayed 401', async () => {
    let releaseRequest: ((response: object) => void) | undefined;
    const pendingResponse = new Promise<object>((resolve) => {
      releaseRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pendingResponse);
    vi.stubGlobal('fetch', fetchMock);
    const unauthorized = vi.fn();
    window.addEventListener('auth:unauthorized', unauthorized);

    const request = apiClient.get('/contacts');
    markAuthSessionActive();
    releaseRequest?.({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ message: 'Old session expired' }),
    });

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(unauthorized).not.toHaveBeenCalled();
    window.removeEventListener('auth:unauthorized', unauthorized);
  });

  it('does not retry account A request with account B after a refresh race', async () => {
    let releaseRefresh: (() => void) | undefined;
    const refreshResponse = new Promise<{ ok: boolean; status: number; json: () => Promise<object> }>((resolve) => {
      releaseRefresh = () => resolve({ ok: true, status: 200, json: async () => ({ access_token: ACCESS_TOKEN }) });
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) })
      .mockReturnValueOnce(refreshResponse);
    vi.stubGlobal('fetch', fetchMock);

    const request = apiClient.get('/contacts');
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    markAuthSessionActive();
    releaseRefresh?.();

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('treats same-user logout and login as a new session generation', async () => {
    let releaseRequest: ((response: object) => void) | undefined;
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise<object>((resolve) => {
      releaseRequest = resolve;
    })));

    const oldRequest = apiClient.get('/contacts');
    invalidateAuthSession();
    markAuthSessionActive();
    releaseRequest?.({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: vi.fn().mockResolvedValue([{ id: 'old-session-contact' }]),
    });

    await expect(oldRequest).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('invalidates captured mutation ownership across logout and same-user login', () => {
    const oldGeneration = captureAuthSessionGeneration();
    expect(isAuthSessionGenerationCurrent(oldGeneration)).toBe(true);

    invalidateAuthSession();
    expect(isAuthSessionGenerationCurrent(oldGeneration)).toBe(false);
    markAuthSessionActive();
    expect(isAuthSessionGenerationCurrent(oldGeneration)).toBe(false);
  });

  it('blocks new refresh attempts while explicit logout is in progress', async () => {
    invalidateAuthSession();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.get('/users')).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('preserves FormData when retrying after refresh', async () => {
    const body = new FormData();
    body.append('file', new Blob(['logo']), 'logo.txt');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ access_token: ACCESS_TOKEN }) })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: vi.fn().mockResolvedValue({ status: 'ok' }),
      });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.post('/organizations/branding', body);

    expect(fetchMock.mock.calls[0][1]?.body).toBe(body);
    expect(fetchMock.mock.calls[2][1]?.body).toBe(body);
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).has('Content-Type')).toBe(false);
  });

  it('rejects a request when the server does not respond before the timeout', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation((_url: string, options?: RequestInit) =>
      new Promise((_resolve, reject) => {
        options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const request = apiClient.get('/auth/me');
    const rejection = expect(request).rejects.toMatchObject({ kind: 'timeout' });
    await vi.advanceTimersByTimeAsync(API_REQUEST_TIMEOUT_MS);

    await rejection;
    vi.useRealTimers();
  });
});
