import { getOrganizationContext } from '@/lib/organization-context';

// Central API Client for CRM Backend Integration (FastAPI)
const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export const API_REQUEST_TIMEOUT_MS = 15_000;
const REFRESH_REQUEST_TIMEOUT_MS = 10_000;
const REFRESH_LOCK_KEY = 'crm:auth-refresh-lock';
const REFRESH_RESULT_KEY = 'crm:auth-refresh-result';
const REFRESH_LOCK_TTL_MS = 12_000;

export function resolveApiBaseUrl(
  configuredUrl = process.env.NEXT_PUBLIC_API_URL,
  environment = process.env.NODE_ENV,
): string {
  const normalizedUrl = configuredUrl?.trim();
  if (normalizedUrl) return normalizedUrl;
  if (environment === 'production') {
    throw new Error('NEXT_PUBLIC_API_URL must be configured for production.');
  }
  return DEFAULT_API_URL;
}

export const BASE_URL = resolveApiBaseUrl();

const NON_REFRESHABLE_AUTH_ENDPOINTS = [
  '/public/quotes/',
  '/public/invoices/',
  '/auth/login',
  '/auth/register',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/accept-invite',
  '/auth/invitations/',
  '/auth/logout',
  '/auth/refresh-token',
  '/auth/oauth/',
  '/auth/magic-link/',
];

let refreshRequest: Promise<boolean> | null = null;
let refreshController: AbortController | null = null;
let authGeneration = 0;
let explicitLogoutInProgress = false;
let refreshChannel: BroadcastChannel | null = null;

function getRefreshChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') return null;
  refreshChannel ??= new BroadcastChannel('crm-auth-session');
  return refreshChannel;
}

/**
 * Invalidate the current browser session before an explicit logout starts.
 *
 * The generation check protects against stale refresh completions, while the
 * abort signal prevents an in-flight refresh from installing new cookies when
 * the browser supports cancellation of the fetch response.
 */
export function invalidateAuthSession(): void {
  authGeneration += 1;
  explicitLogoutInProgress = true;
  refreshController?.abort();
}

/** Re-enable refresh after a new login/session has been established. */
export function markAuthSessionActive(): void {
  authGeneration += 1;
  explicitLogoutInProgress = false;
}

export function clearSessionToken(): void {
  if (typeof window === 'undefined') return;
  // Remove legacy browser-readable tokens during the HttpOnly-cookie migration.
  sessionStorage.removeItem('token');
  localStorage.removeItem('token');
  sessionStorage.removeItem('user');
  localStorage.removeItem('user');
}

export interface ApiRequestOptions extends RequestInit {
  timeoutMs?: number;
}

export interface ApiClient {
  <T>(endpoint: string, options?: ApiRequestOptions): Promise<T>;
  get<T>(endpoint: string, options?: ApiRequestOptions): Promise<T>;
  getWithMetadata<T>(endpoint: string, options?: ApiRequestOptions): Promise<ApiResponse<T>>;
  post<T>(endpoint: string, data?: unknown, options?: ApiRequestOptions): Promise<T>;
  put<T>(endpoint: string, data?: unknown, options?: ApiRequestOptions): Promise<T>;
  patch<T>(endpoint: string, data?: unknown, options?: ApiRequestOptions): Promise<T>;
  delete<T>(endpoint: string, options?: ApiRequestOptions): Promise<T>;
}

export interface ApiResponse<T> {
  data: T;
  headers: Headers;
  status: number;
}

export type ApiErrorKind = 'http' | 'network' | 'timeout';

export class ApiError extends Error {
  readonly status: number | null;
  readonly kind: ApiErrorKind;
  readonly code: string | null;
  readonly fields: Record<string, unknown> | null;

  constructor(
    message: string,
    kind: ApiErrorKind,
    status: number | null = null,
    code: string | null = null,
    fields: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

async function throwResponseError(response: Response, redirectUnauthorized = true, organizationId: string | null = null): Promise<never> {
  const errorData = await response.json().catch(() => ({}));
  if (response.status === 401 && redirectUnauthorized) handleUnauthorized(errorData.code);
  if (errorData.code === 'ORGANIZATION_UNAVAILABLE' && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('organization:unavailable', { detail: organizationId }));
  }
  throw new ApiError(
    errorData.detail || errorData.message || 'An unexpected error occurred',
    'http',
    response.status,
    typeof errorData.code === 'string' ? errorData.code : null,
    errorData.fields && typeof errorData.fields === 'object' ? errorData.fields : null,
  );
}

function canRefresh(endpoint: string): boolean {
  return !NON_REFRESHABLE_AUTH_ENDPOINTS.some((authEndpoint) =>
    endpoint.startsWith(authEndpoint),
  );
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const callerSignal = init.signal;
  const abortFromCaller = () => controller.abort(callerSignal?.reason);

  callerSignal?.addEventListener('abort', abortFromCaller, { once: true });
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (timedOut) {
      throw new ApiError('The request timed out. Please try again.', 'timeout');
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw error;
    }
    throw new ApiError('Unable to reach the server. Please check your connection.', 'network');
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener('abort', abortFromCaller);
  }
}

async function refreshSession(generation: number, signal: AbortSignal): Promise<boolean> {
  if (explicitLogoutInProgress || generation !== authGeneration) return false;
  try {
    const response = await fetchWithTimeout(`${BASE_URL}/auth/refresh-token`, {
      method: 'POST',
      credentials: 'include',
      signal,
    }, REFRESH_REQUEST_TIMEOUT_MS);
    return response.ok && !explicitLogoutInProgress && generation === authGeneration;
  } catch {
    return false;
  }
}

async function waitForOtherTabRefresh(): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  const started = Date.now();
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      window.removeEventListener('storage', onStorage);
      getRefreshChannel()?.removeEventListener('message', onMessage);
      clearInterval(timer);
      clearTimeout(timeout);
      resolve(value);
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === REFRESH_RESULT_KEY && event.newValue) {
        try {
          const result = JSON.parse(event.newValue) as { at?: number; ok?: boolean };
          if (result.at && result.at >= started) finish(result.ok === true);
        } catch { /* ignore malformed coordination state */ }
      }
    };
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === 'refresh-result' && event.data.at >= started) {
        finish(event.data.ok === true);
      }
    };
    const timer = window.setInterval(() => {
      const raw = localStorage.getItem(REFRESH_LOCK_KEY);
      if (!raw) {
        try {
          const result = JSON.parse(localStorage.getItem(REFRESH_RESULT_KEY) || '{}') as {
            at?: number;
            ok?: boolean;
          };
          finish(result.at && result.at >= started ? result.ok === true : false);
        } catch { finish(false); }
      }
      else {
        try {
          if (Date.now() - Number(JSON.parse(raw).at) > REFRESH_LOCK_TTL_MS) finish(false);
        } catch { finish(false); }
      }
    }, 100);
    const timeout = window.setTimeout(() => finish(false), REFRESH_LOCK_TTL_MS + 1000);
    window.addEventListener('storage', onStorage);
    getRefreshChannel()?.addEventListener('message', onMessage);
  });
}

async function coordinatedRefresh(generation: number, signal: AbortSignal): Promise<boolean> {
  if (typeof window === 'undefined') return refreshSession(generation, signal);
  const now = Date.now();
  const existing = localStorage.getItem(REFRESH_LOCK_KEY);
  if (existing) {
    try {
      if (now - Number(JSON.parse(existing).at) <= REFRESH_LOCK_TTL_MS) {
        return waitForOtherTabRefresh();
      }
    } catch { /* stale lock */ }
  }
  const lockId = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${now}-${Math.random()}`;
  const lock = JSON.stringify({ at: now, id: lockId });
  localStorage.setItem(REFRESH_LOCK_KEY, lock);
  // Re-read after writing to avoid two tabs both assuming ownership.
  if (localStorage.getItem(REFRESH_LOCK_KEY) !== lock) return waitForOtherTabRefresh();
  let ok = false;
  try {
    ok = await refreshSession(generation, signal);
    return ok;
  } finally {
    const result = JSON.stringify({ at: Date.now(), ok });
    localStorage.setItem(REFRESH_RESULT_KEY, result);
    getRefreshChannel()?.postMessage({ type: 'refresh-result', ...JSON.parse(result) });
    if (localStorage.getItem(REFRESH_LOCK_KEY) === lock) localStorage.removeItem(REFRESH_LOCK_KEY);
  }
}

function getRefreshRequest(): Promise<boolean> {
  if (explicitLogoutInProgress) return Promise.resolve(false);
  if (!refreshRequest) {
    const generation = authGeneration;
    refreshController = new AbortController();
    refreshRequest = coordinatedRefresh(generation, refreshController.signal).finally(() => {
      refreshRequest = null;
      refreshController = null;
    });
  }
  return refreshRequest;
}

function handleUnauthorized(code?: string): void {
  if (typeof window === 'undefined') return;
  clearSessionToken();
  window.dispatchEvent(new Event('auth:unauthorized'));
  if (code === 'AUTH_ACCOUNT_INACTIVE') {
    window.location.href = '/inactive';
    return;
  }
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function request<T>(
  endpoint: string,
  options: ApiRequestOptions = {},
  allowRefresh = true,
): Promise<ApiResponse<T>> {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  const organizationId = getOrganizationContext();
  const platformOperation = endpoint.startsWith('/organizations/all') || endpoint.startsWith('/organizations/deletions/')
    || (endpoint === '/organizations' && options.method === 'POST')
    || (/^\/organizations\/[^/]+$/.test(endpoint) && options.method === 'DELETE')
    || endpoint === '/organizations/invitations/new-organization';
  if (organizationId && !endpoint.startsWith('/auth/') && !platformOperation) {
    headers['X-Organization-ID'] = organizationId;
  }
  if (organizationId && endpoint === '/auth/me') headers['X-Organization-ID'] = organizationId;

  if (isFormData) {
    delete headers['Content-Type'];
  } else if (!headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  let response = await fetchWithTimeout(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: options.credentials ?? 'include',
  }, options.timeoutMs ?? API_REQUEST_TIMEOUT_MS);

  if (response.status === 401 && allowRefresh && canRefresh(endpoint)) {
    const refreshed = await getRefreshRequest();
    if (refreshed && !explicitLogoutInProgress) {
      response = await fetchWithTimeout(`${BASE_URL}${endpoint}`, {
        ...options,
        headers,
        credentials: options.credentials ?? 'include',
      }, options.timeoutMs ?? API_REQUEST_TIMEOUT_MS);
    }
  }

  if (!response.ok) {
    return throwResponseError(response, !endpoint.startsWith('/public/'), headers['X-Organization-ID'] ?? null);
  }

  return {
    data: await response.json(),
    headers: response.headers,
    status: response.status,
  };
}

export async function openApiStream(
  endpoint: string,
  data: unknown,
  signal?: AbortSignal,
): Promise<Response> {
  const organizationId = getOrganizationContext();
  const options: RequestInit = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json', Accept: 'text/event-stream',
      ...(organizationId ? { 'X-Organization-ID': organizationId } : {}),
    },
    body: JSON.stringify(data),
    credentials: 'include',
    signal,
  };
  let response = await fetchWithTimeout(
    `${BASE_URL}${endpoint}`,
    options,
    API_REQUEST_TIMEOUT_MS,
  );
  if (response.status === 401 && canRefresh(endpoint) && (await getRefreshRequest())) {
    response = await fetchWithTimeout(
      `${BASE_URL}${endpoint}`,
      options,
      API_REQUEST_TIMEOUT_MS,
    );
  }
  if (!response.ok) return throwResponseError(response, true, organizationId);
  return response;
}

const mainClient = async function <T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const response = await request<T>(endpoint, options);
  return response.data;
} as ApiClient;

mainClient.get = function <T>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
  return mainClient<T>(endpoint, { ...options, method: 'GET' });
};

mainClient.getWithMetadata = function <T>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<ApiResponse<T>> {
  return request<T>(endpoint, { ...options, method: 'GET' });
};

mainClient.post = function <T>(endpoint: string, data?: unknown, options: ApiRequestOptions = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && data instanceof FormData;
  return mainClient<T>(endpoint, {
    ...options,
    method: 'POST',
    body: isFormData ? data : data ? JSON.stringify(data) : undefined,
  });
};

mainClient.put = function <T>(endpoint: string, data?: unknown, options: ApiRequestOptions = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && data instanceof FormData;
  return mainClient<T>(endpoint, {
    ...options,
    method: 'PUT',
    body: isFormData ? data : data ? JSON.stringify(data) : undefined,
  });
};

mainClient.patch = function <T>(endpoint: string, data?: unknown, options: ApiRequestOptions = {}): Promise<T> {
  return mainClient<T>(endpoint, {
    ...options,
    method: 'PATCH',
    body: data ? JSON.stringify(data) : undefined,
  });
};

mainClient.delete = function <T>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
  return mainClient<T>(endpoint, { ...options, method: 'DELETE' });
};

export const apiClient = mainClient;
