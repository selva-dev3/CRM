import { useQuery } from '@tanstack/react-query';

import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

export const ACTIVITY_MODULES = [
  'leads',
  'deals',
  'tasks',
  'meetings',
  'calls',
  'emails',
  'notes',
  'calendar',
  'whatsapp',
] as const;

export type ActivityModule = (typeof ACTIVITY_MODULES)[number];

export interface ActivityItem {
  id: string;
  module: ActivityModule;
  action: string;
  description?: string | null;
  entity_type: string;
  entity_id: string;
  actor_id?: string | null;
  occurred_at: string;
  href: string;
}

export interface ActivityListParams {
  page?: number;
  limit?: number;
  module?: ActivityModule;
  search?: string;
}

export async function fetchActivitiesPageApi(
  params: ActivityListParams = {},
): Promise<PaginatedResult<ActivityItem>> {
  const query = new URLSearchParams({
    page: String(params.page ?? 1),
    limit: String(params.limit ?? 20),
  });
  if (params.module) query.set('module', params.module);
  if (params.search) query.set('search', params.search);
  return fetchPaginated<ActivityItem>(`/activities?${query.toString()}`);
}

export function useActivitiesPageQuery(params: ActivityListParams) {
  return useQuery({
    queryKey: ['activities', params],
    queryFn: () => fetchActivitiesPageApi(params),
    placeholderData: (previousData) => previousData,
  });
}
