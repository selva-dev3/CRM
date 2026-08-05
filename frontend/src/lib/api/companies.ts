import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface CompanyItem {
  id: string;
  name: string;
  domain?: string;
  website?: string;
  industry?: string;
  size?: string;
  employee_count?: number;
  created_at?: string;
}

export interface CompanyCreatePayload {
  name: string;
  domain?: string;
  website?: string;
  industry?: string;
  size?: string;
  employee_count?: number;
}

export interface CompanyUpdatePayload {
  name?: string;
  domain?: string;
  website?: string;
  industry?: string;
  size?: string;
  employee_count?: number;
}

// API Functions
export async function fetchCompaniesApi(page = 1, limit = 15, search?: string): Promise<CompanyItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<CompanyItem[]>(`/companies?${query.toString()}`);
    if (Array.isArray(data)) return data;
  } catch (error) {
    console.error('Failed to fetch companies:', error);
  }
  return [];
}

export async function createCompanyApi(payload: CompanyCreatePayload): Promise<CompanyItem> {
  const empCount = payload.employee_count ?? (payload.size ? parseInt(payload.size, 10) : undefined);
  return apiClient.post<CompanyItem>('/companies', {
    name: payload.name,
    domain: payload.domain || payload.website || undefined,
    website: payload.website || payload.domain || undefined,
    industry: payload.industry || undefined,
    size: payload.size || (empCount ? String(empCount) : undefined),
    employee_count: empCount,
  });
}

export async function updateCompanyApi(payload: { id: string; data: CompanyUpdatePayload }): Promise<CompanyItem> {
  const empCount = payload.data.employee_count ?? (payload.data.size ? parseInt(payload.data.size, 10) : undefined);
  return apiClient.put<CompanyItem>(`/companies/${payload.id}`, {
    ...payload.data,
    employee_count: empCount,
  });
}

export async function deleteCompanyApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/companies/${id}`);
}

export async function bulkDeleteCompaniesApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post<{ affected_count: number; message: string }>('/companies/bulk-delete', { ids });
}

export async function exportCompaniesCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/companies/export/csv');
}

export async function importCompaniesCsvApi(): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/companies/import/csv');
}

export async function lookupCompanyDomainApi(domain: string): Promise<any> {
  return apiClient.post(`/companies/lookup-domain?domain=${encodeURIComponent(domain)}`);
}

export async function getCompanyApi(id: string): Promise<CompanyItem> {
  return apiClient.get<CompanyItem>(`/companies/${id}`);
}

export async function getCompanyContactsApi(id: string): Promise<any[]> {
  try {
    return await apiClient.get<any[]>(`/companies/${id}/contacts`);
  } catch {
    return [];
  }
}

export async function getCompanyDealsApi(id: string): Promise<any[]> {
  try {
    return await apiClient.get<any[]>(`/companies/${id}/deals`);
  } catch {
    return [];
  }
}

export async function getCompanyNotesApi(id: string): Promise<any[]> {
  try {
    return await apiClient.get<any[]>(`/companies/${id}/notes`);
  } catch {
    return [];
  }
}

export async function addCompanyNoteApi(payload: { id: string; content: string }): Promise<any> {
  return apiClient.post(`/companies/${payload.id}/notes?content=${encodeURIComponent(payload.content)}`, {
    content: payload.content,
  });
}

export async function getCompanyQuotesApi(id: string): Promise<any[]> {
  try {
    return await apiClient.get<any[]>(`/companies/${id}/quotes`);
  } catch {
    return [];
  }
}

export async function getCompanyInvoicesApi(id: string): Promise<any[]> {
  try {
    return await apiClient.get<any[]>(`/companies/${id}/invoices`);
  } catch {
    return [];
  }
}

export async function getCompanyDocumentsApi(id: string): Promise<any[]> {
  try {
    return await apiClient.get<any[]>(`/companies/${id}/documents`);
  } catch {
    return [];
  }
}

export async function getCompanyHierarchyApi(id: string): Promise<any> {
  try {
    return await apiClient.get<any>(`/companies/${id}/hierarchy`);
  } catch {
    return null;
  }
}

// TanStack Query & Mutation Hooks
export function useCompaniesQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['companies', page, limit, search],
    queryFn: () => fetchCompaniesApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}

export function useCompanyQuery(id: string) {
  return useQuery({
    queryKey: ['company', id],
    queryFn: () => getCompanyApi(id),
    enabled: !!id,
  });
}

export function useCreateCompanyMutation() {
  return useMutation({
    mutationFn: createCompanyApi,
  });
}

export function useUpdateCompanyMutation() {
  return useMutation({
    mutationFn: updateCompanyApi,
  });
}

export function useDeleteCompanyMutation() {
  return useMutation({
    mutationFn: deleteCompanyApi,
  });
}

export function useBulkDeleteCompaniesMutation() {
  return useMutation({
    mutationFn: bulkDeleteCompaniesApi,
  });
}

export function useImportCompaniesCsvMutation() {
  return useMutation({
    mutationFn: importCompaniesCsvApi,
  });
}
