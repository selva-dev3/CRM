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
});
