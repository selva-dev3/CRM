// Central API Client for CRM Backend Integration (FastAPI)
const DEFAULT_API_URL = 'https://crm-dev3.up.railway.app/api/v1';

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || 'An unexpected error occurred');
  }

  return response.json();
}
