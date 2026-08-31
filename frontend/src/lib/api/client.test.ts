import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient, clearSessionToken } from './client';

describe('apiClient cookie authentication', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    sessionStorage.clear();
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
});
