import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { CompanyHierarchy } from '@/lib/types';
import type { CustomFieldValue } from '@/lib/api/custom-fields';
import type { DealItem } from '@/lib/api/deals';
import type { DocumentItem } from '@/lib/api/documents';
import type { InvoiceItem } from '@/lib/api/invoices';
import type { NoteItem } from '@/lib/api/notes';
import type { QuoteItem } from '@/lib/api/quotes';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

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

export interface CompanyContactItem {
  id: string;
  name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  email: string;
  phone?: string | null;
  position?: string | null;
  company_id?: string | null;
  created_at?: string | null;
}

export const companyKeys = {
  list: (page: number, limit: number, search?: string) =>
    ['companies', page, limit, search] as const,
  page: (page: number, limit: number, search?: string) =>
    ['companies-page', page, limit, search] as const,
  detail: (id: string) => ['company', id] as const,
  contacts: (id: string, page?: number, limit?: number) => ['company-contacts', id, page, limit] as const,
  deals: (id: string, page?: number, limit?: number) => ['company-deals', id, page, limit] as const,
  notes: (id: string, page?: number, limit?: number) => ['company-notes', id, page, limit] as const,
  quotes: (id: string, page?: number, limit?: number) => ['company-quotes', id, page, limit] as const,
  invoices: (id: string, page?: number, limit?: number) => ['company-invoices', id, page, limit] as const,
  documents: (id: string) => ['company-documents', id] as const,
  hierarchy: (id: string) => ['company-hierarchy', id] as const,
};

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

export async function getCompanyContactsApi(id: string, page = 1, limit = 15): Promise<PaginatedResult<CompanyContactItem>> {
  return fetchPaginated<CompanyContactItem>(`/companies/${id}/contacts?page=${page}&limit=${limit}`);
}

export async function getCompanyDealsApi(id: string, page = 1, limit = 15): Promise<PaginatedResult<DealItem>> {
  return fetchPaginated<DealItem>(`/companies/${id}/deals?page=${page}&limit=${limit}`);
}

export async function getCompanyNotesApi(id: string, page = 1, limit = 15): Promise<PaginatedResult<NoteItem>> {
  return fetchPaginated<NoteItem>(`/companies/${id}/notes?page=${page}&limit=${limit}`);
}

export async function addCompanyNoteApi(payload: { id: string; content: string }): Promise<NoteItem> {
  return apiClient.post<NoteItem>(`/companies/${payload.id}/notes?content=${encodeURIComponent(payload.content)}`, {
    content: payload.content,
  });
}

export async function getCompanyQuotesApi(id: string, page = 1, limit = 15): Promise<PaginatedResult<QuoteItem>> {
  return fetchPaginated<QuoteItem>(`/companies/${id}/quotes?page=${page}&limit=${limit}`);
}

export async function getCompanyInvoicesApi(id: string, page = 1, limit = 15): Promise<PaginatedResult<InvoiceItem>> {
  return fetchPaginated<InvoiceItem>(`/companies/${id}/invoices?page=${page}&limit=${limit}`);
}

export async function getCompanyDocumentsApi(id: string): Promise<DocumentItem[]> {
  return apiClient.get<DocumentItem[]>(`/companies/${id}/documents`);
}

export async function getCompanyHierarchyApi(id: string): Promise<CompanyHierarchy | null> {
  return apiClient.get<CompanyHierarchy>(`/companies/${id}/hierarchy`);
}

// TanStack Query & Mutation Hooks
export function useCompaniesQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: companyKeys.list(page, limit, search),
    queryFn: () => fetchCompaniesApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}

export function useCompaniesPageQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: companyKeys.page(page, limit, search),
    queryFn: () => fetchCompaniesPageApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}

export function useCompanyQuery(id: string) {
  return useQuery({
    queryKey: companyKeys.detail(id),
    queryFn: () => getCompanyApi(id),
    enabled: !!id,
  });
}

export function useCompanyContactsQuery(id: string, enabled = true, page = 1, limit = 15) {
  return useQuery({
    queryKey: companyKeys.contacts(id, page, limit),
    queryFn: () => getCompanyContactsApi(id, page, limit),
    enabled: Boolean(id) && enabled,
  });
}

export function useCompanyDealsQuery(id: string, enabled = true, page = 1, limit = 15) {
  return useQuery({
    queryKey: companyKeys.deals(id, page, limit),
    queryFn: () => getCompanyDealsApi(id, page, limit),
    enabled: Boolean(id) && enabled,
  });
}

export function useCompanyNotesQuery(id: string, enabled = true, page = 1, limit = 15) {
  return useQuery({
    queryKey: companyKeys.notes(id, page, limit),
    queryFn: () => getCompanyNotesApi(id, page, limit),
    enabled: Boolean(id) && enabled,
  });
}

export function useCompanyQuotesQuery(id: string, enabled = true, page = 1, limit = 15) {
  return useQuery({
    queryKey: companyKeys.quotes(id, page, limit),
    queryFn: () => getCompanyQuotesApi(id, page, limit),
    enabled: Boolean(id) && enabled,
  });
}

export function useCompanyInvoicesQuery(id: string, enabled = true, page = 1, limit = 15) {
  return useQuery({
    queryKey: companyKeys.invoices(id, page, limit),
    queryFn: () => getCompanyInvoicesApi(id, page, limit),
    enabled: Boolean(id) && enabled,
  });
}

export function useCompanyDocumentsQuery(id: string, enabled = true) {
  return useQuery({
    queryKey: companyKeys.documents(id),
    queryFn: () => getCompanyDocumentsApi(id),
    enabled: Boolean(id) && enabled,
  });
}

export function useCompanyHierarchyQuery(id: string, enabled = true) {
  return useQuery({
    queryKey: companyKeys.hierarchy(id),
    queryFn: () => getCompanyHierarchyApi(id),
    enabled: Boolean(id) && enabled,
  });
}

export function useAddCompanyNoteMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => addCompanyNoteApi({ id, content }),
    onSuccess: (note) => {
      void note;
      queryClient.invalidateQueries({ queryKey: ['company-notes', id] });
    },
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
