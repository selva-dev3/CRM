// Central API Client for CRM Backend Integration (FastAPI)
const DEFAULT_API_URL = 'http://localhost:8000/api/v1';

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

export function clearSessionToken(): void {
  if (typeof window === 'undefined') return;
  // Remove legacy browser-readable tokens during the HttpOnly-cookie migration.
  sessionStorage.removeItem('token');
  localStorage.removeItem('token');
  sessionStorage.removeItem('user');
  localStorage.removeItem('user');
}

export interface ApiClient {
  <T>(endpoint: string, options?: RequestInit): Promise<T>;
  get<T>(endpoint: string, options?: RequestInit): Promise<T>;
  getWithMetadata<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>>;
  post<T>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T>;
  put<T>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T>;
  delete<T>(endpoint: string, options?: RequestInit): Promise<T>;
}

export interface ApiResponse<T> {
  data: T;
  headers: Headers;
  status: number;
}

function canRefresh(endpoint: string): boolean {
  return !NON_REFRESHABLE_AUTH_ENDPOINTS.some((authEndpoint) =>
    endpoint.startsWith(authEndpoint),
  );
}

async function refreshSession(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/auth/refresh-token`, {
      method: 'POST',
      credentials: 'include',
    });
    return response.ok;
  } catch {
    return false;
  }
}

function getRefreshRequest(): Promise<boolean> {
  if (!refreshRequest) {
    refreshRequest = refreshSession().finally(() => {
      refreshRequest = null;
    });
  }
  return refreshRequest;
}

function handleUnauthorized(): void {
  if (typeof window === 'undefined') return;
  clearSessionToken();
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  allowRefresh = true,
): Promise<ApiResponse<T>> {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (isFormData) {
    delete headers['Content-Type'];
  } else if (!headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  let response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && allowRefresh && canRefresh(endpoint)) {
    const refreshed = await getRefreshRequest();
    if (refreshed) {
      response = await fetch(`${BASE_URL}${endpoint}`, {
        ...options,
        headers,
        credentials: 'include',
      });
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      handleUnauthorized();
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || 'An unexpected error occurred');
  }

  return {
    data: await response.json(),
    headers: response.headers,
    status: response.status,
  };
}

const mainClient = async function <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await request<T>(endpoint, options);
  return response.data;
} as ApiClient;

mainClient.get = function <T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  return mainClient<T>(endpoint, { ...options, method: 'GET' });
};

mainClient.getWithMetadata = function <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  return request<T>(endpoint, { ...options, method: 'GET' });
};

mainClient.post = function <T>(endpoint: string, data?: unknown, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && data instanceof FormData;
  return mainClient<T>(endpoint, {
    ...options,
    method: 'POST',
    body: isFormData ? data : data ? JSON.stringify(data) : undefined,
  });
};

mainClient.put = function <T>(endpoint: string, data?: unknown, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && data instanceof FormData;
  return mainClient<T>(endpoint, {
    ...options,
    method: 'PUT',
    body: isFormData ? data : data ? JSON.stringify(data) : undefined,
  });
};

mainClient.delete = function <T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  return mainClient<T>(endpoint, { ...options, method: 'DELETE' });
};

export const apiClient = mainClient;
