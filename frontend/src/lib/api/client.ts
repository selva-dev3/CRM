// Central API Client for CRM Backend Integration (FastAPI)
const DEFAULT_API_URL = 'https://crm-dev3.up.railway.app/api/v1';

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;

export function getSessionToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('token') || localStorage.getItem('token');
}

export function setSessionToken(token: string, remember: boolean = true): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem('token', token);
  if (remember) {
    localStorage.setItem('token', token);
    document.cookie = `token=${token}; path=/; max-age=86400; SameSite=Lax`;
  }
}

export function clearSessionToken(): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem('token');
  localStorage.removeItem('token');
  sessionStorage.removeItem('user');
  localStorage.removeItem('user');
  document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
  document.cookie = 'user=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
}

export interface ApiClient {
  <T>(endpoint: string, options?: RequestInit): Promise<T>;
  get<T>(endpoint: string, options?: RequestInit): Promise<T>;
  post<T>(endpoint: string, data?: any, options?: RequestInit): Promise<T>;
  put<T>(endpoint: string, data?: any, options?: RequestInit): Promise<T>;
  delete<T>(endpoint: string, options?: RequestInit): Promise<T>;
}

const mainClient = async function <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getSessionToken();

  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (isFormData) {
    delete headers['Content-Type'];
  } else if (!headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') {
      clearSessionToken();
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || 'An unexpected error occurred');
  }

  return response.json();
} as ApiClient;

mainClient.get = function <T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  return mainClient<T>(endpoint, { ...options, method: 'GET' });
};

mainClient.post = function <T>(endpoint: string, data?: any, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && data instanceof FormData;
  return mainClient<T>(endpoint, {
    ...options,
    method: 'POST',
    body: isFormData ? data : data ? JSON.stringify(data) : undefined,
  });
};

mainClient.put = function <T>(endpoint: string, data?: any, options: RequestInit = {}): Promise<T> {
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
