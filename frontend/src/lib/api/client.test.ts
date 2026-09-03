import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient, BASE_URL, clearSessionToken, resolveApiBaseUrl } from './client';

describe('apiClient cookie authentication', () => {
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

  it('includes credentials without exposing an Authorization token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.get('/auth/me');

    expect(fetchMock).toHaveBeenCalledOnce();
    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.credentials).toBe('include');
    expect(new Headers(options.headers).has('Authorization')).toBe(false);
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
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValue({}) })
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
    const refreshResponse = new Promise<{ ok: boolean; status: number }>((resolve) => {
      releaseRefresh = () => resolve({ ok: true, status: 200 });
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

  it('preserves FormData when retrying after refresh', async () => {
    const body = new FormData();
    body.append('file', new Blob(['logo']), 'logo.txt');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: vi.fn().mockResolvedValue({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValue({}) })
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
});
