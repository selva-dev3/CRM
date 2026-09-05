import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { CompanyHierarchy, RelatedRecord } from '@/lib/types';
import type { CustomFieldValue } from '@/lib/api/custom-fields';

export interface CompanyItem {
  id: string;
  name: string;
  domain?: string;
  website?: string;
  industry?: string;
  size?: string;
  employee_count?: number;
  created_at?: string;
  custom_fields?: Record<string, CustomFieldValue>;
}

export interface CompanyCreatePayload {
  name: string;
  domain?: string;
  website?: string;
  industry?: string;
  size?: string;
  employee_count?: number;
  custom_fields?: Record<string, CustomFieldValue>;
}

export interface CompanyUpdatePayload {
  name?: string;
  domain?: string;
  website?: string;
  industry?: string;
  size?: string;
  employee_count?: number;
  custom_fields?: Record<string, CustomFieldValue>;
}

export interface CompaniesPage {
  items: CompanyItem[];
  total: number;
}

// API Functions
export async function fetchCompaniesPageApi(
  page = 1,
  limit = 15,
  search?: string,
): Promise<CompaniesPage> {
  const query = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (search) query.append('search', search);
  const response = await apiClient.getWithMetadata<CompanyItem[]>(
    `/companies?${query.toString()}`,
  );
  const totalHeader = response.headers.get('X-Total-Count');
  const total = totalHeader === null ? Number.NaN : Number.parseInt(totalHeader, 10);
  if (!Number.isInteger(total) || total < 0) {
    throw new Error('Companies response is missing valid pagination metadata.');
  }
  return { items: response.data, total };
}

export async function fetchCompaniesApi(
  page = 1,
  limit = 15,
  search?: string,
): Promise<CompanyItem[]> {
  return (await fetchCompaniesPageApi(page, limit, search)).items;
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
    custom_fields: payload.custom_fields ?? {},
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

export async function lookupCompanyDomainApi(domain: string): Promise<CompanyItem> {
  return apiClient.post<CompanyItem>(`/companies/lookup-domain?domain=${encodeURIComponent(domain)}`);
}

export async function getCompanyApi(id: string): Promise<CompanyItem> {
  return apiClient.get<CompanyItem>(`/companies/${id}`);
}

export async function getCompanyContactsApi(id: string): Promise<RelatedRecord[]> {
  return apiClient.get<RelatedRecord[]>(`/companies/${id}/contacts`);
}

export async function getCompanyDealsApi(id: string): Promise<RelatedRecord[]> {
  return apiClient.get<RelatedRecord[]>(`/companies/${id}/deals`);
}

export async function getCompanyNotesApi(id: string): Promise<RelatedRecord[]> {
  return apiClient.get<RelatedRecord[]>(`/companies/${id}/notes`);
}

export async function addCompanyNoteApi(payload: { id: string; content: string }): Promise<RelatedRecord> {
  return apiClient.post<RelatedRecord>(`/companies/${payload.id}/notes?content=${encodeURIComponent(payload.content)}`, {
    content: payload.content,
  });
}

export async function getCompanyQuotesApi(id: string): Promise<RelatedRecord[]> {
  return apiClient.get<RelatedRecord[]>(`/companies/${id}/quotes`);
}

export async function getCompanyInvoicesApi(id: string): Promise<RelatedRecord[]> {
  return apiClient.get<RelatedRecord[]>(`/companies/${id}/invoices`);
}

export async function getCompanyDocumentsApi(id: string): Promise<RelatedRecord[]> {
  return apiClient.get<RelatedRecord[]>(`/companies/${id}/documents`);
}

export async function getCompanyHierarchyApi(id: string): Promise<CompanyHierarchy | null> {
  return apiClient.get<CompanyHierarchy>(`/companies/${id}/hierarchy`);
}

// TanStack Query & Mutation Hooks
export function useCompaniesQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['companies', page, limit, search],
    queryFn: () => fetchCompaniesApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}

export function useCompaniesPageQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['companies-page', page, limit, search],
    queryFn: () => fetchCompaniesPageApi(page, limit, search),
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
