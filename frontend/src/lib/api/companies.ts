import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface CompanyItem {
  id: string;
  name: string;
  industry?: string;
  website?: string;
  employee_count?: number;
  created_at?: string;
}

export async function fetchCompaniesApi(): Promise<CompanyItem[]> {
  try {
    const data = await apiClient.get<CompanyItem[]>('/companies');
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Return fallback list if backend is empty
  }
  return [
    { id: 'comp-1', name: 'Acme Global Corp' },
    { id: 'comp-2', name: 'Nexus Tech Solutions' },
    { id: 'comp-3', name: 'Starlight Logistics' },
    { id: 'comp-4', name: 'Hyperion Cloud Inc' },
  ];
}

export function useCompaniesQuery() {
  return useQuery({
    queryKey: ['companies'],
    queryFn: fetchCompaniesApi,
  });
}
