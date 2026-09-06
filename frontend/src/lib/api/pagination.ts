import { apiClient } from '@/lib/api/client';

export interface PaginatedResult<T> {
  items: T[];
  total: number;
}

export async function fetchPaginated<T>(endpoint: string): Promise<PaginatedResult<T>> {
  const response = await apiClient.getWithMetadata<T[]>(endpoint);
  const rawTotal = response.headers.get('X-Total-Count');
  const total = rawTotal === null || rawTotal.trim() === '' ? Number.NaN : Number(rawTotal);

  if (!Number.isSafeInteger(total) || total < 0) {
    throw new Error(`Missing or invalid X-Total-Count header for ${endpoint}`);
  }

  return { items: response.data, total };
}
