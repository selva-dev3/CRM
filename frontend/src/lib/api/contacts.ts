import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { RelatedRecord } from '@/lib/types';
import type { CustomFieldValue } from '@/lib/api/custom-fields';

export interface ContactItem {
  id: string;
  name: string;
  email: string;
  phone?: string;
  position?: string;
  company_id?: string;
  is_starred?: boolean;
  status?: string;
  created_at?: string;
  custom_fields?: Record<string, CustomFieldValue>;
}

export interface ContactCreatePayload {
  first_name?: string;
  last_name?: string;
  name: string;
  email: string;
  phone?: string;
  company_id?: string;
  position?: string;
  job_title?: string;
  custom_fields?: Record<string, CustomFieldValue>;
}

export interface ContactUpdatePayload {
  first_name?: string;
  last_name?: string;
  name?: string;
  email?: string;
  phone?: string;
  company_id?: string;
  position?: string;
  job_title?: string;
  custom_fields?: Record<string, CustomFieldValue>;
}

// API Functions
export async function fetchContactsApi(page = 1, limit = 15, search?: string): Promise<ContactItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<ContactItem[]>(`/contacts?${query.toString()}`);
    if (Array.isArray(data)) return data;
  } catch (error) {
    console.error('Failed to fetch contacts:', error);
  }
  return [];
}

export async function createContactApi(payload: ContactCreatePayload): Promise<ContactItem> {
  const parts = payload.name.trim().split(' ');
  const firstName = payload.first_name || parts[0] || payload.name;
  const lastName = payload.last_name || parts.slice(1).join(' ') || parts[0] || 'Contact';

  return apiClient.post<ContactItem>('/contacts', {
    first_name: firstName,
    last_name: lastName,
    name: payload.name,
    email: payload.email,
    phone: payload.phone || null,
    company_id: payload.company_id || null,
    position: payload.position || 'Representative',
    job_title: payload.job_title || payload.position || 'Representative',
    custom_fields: payload.custom_fields ?? {},
  });
}

export async function fetchStarredContactsApi(): Promise<ContactItem[]> {
  try {
    const data = await apiClient.get<ContactItem[]>('/contacts/starred');
    if (Array.isArray(data)) return data;
  } catch {
    // Fallback empty
  }
  return [];
}

export async function mergeContactsApi(payload: { primaryId: string; secondaryId: string }): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(
    `/contacts/merge?primary_id=${encodeURIComponent(payload.primaryId)}&secondary_id=${encodeURIComponent(payload.secondaryId)}`
  );
}

export async function exportContactsCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/contacts/export/csv');
}

export async function importContactsCsvApi(): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/contacts/import/csv');
}

export async function bulkDeleteContactsApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post<{ affected_count: number; message: string }>('/contacts/bulk-delete', { ids });
}

export async function getContactByIdApi(id: string): Promise<ContactItem> {
  return apiClient.get<ContactItem>(`/contacts/${id}`);
}

export async function updateContactApi(payload: { id: string; data: ContactUpdatePayload }): Promise<ContactItem> {
  return apiClient.put<ContactItem>(`/contacts/${payload.id}`, payload.data);
}

export async function deleteContactApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/contacts/${id}`);
}

export async function starContactApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/contacts/${id}/star`);
}

export async function unstarContactApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/contacts/${id}/unstar`);
}

export async function getContactDealsApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/contacts/${id}/deals`);
  } catch {
    return [];
  }
}

export async function getContactActivitiesApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/contacts/${id}/activities`);
  } catch {
    return [];
  }
}

export async function getContactNotesApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/contacts/${id}/notes`);
  } catch {
    return [];
  }
}

export async function addContactNoteApi(payload: { id: string; content: string }): Promise<RelatedRecord> {
  return apiClient.post<RelatedRecord>(`/contacts/${payload.id}/notes?content=${encodeURIComponent(payload.content)}`, {
    content: payload.content,
  });
}

export async function getContactEmailsApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/contacts/${id}/emails`);
  } catch {
    return [];
  }
}

export async function getContactCallsApi(id: string): Promise<RelatedRecord[]> {
  try {
    return await apiClient.get<RelatedRecord[]>(`/contacts/${id}/calls`);
  } catch {
    return [];
  }
}

// TanStack Query & Mutation Hooks
export function useContactsQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['contacts', page, limit, search],
    queryFn: () => fetchContactsApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}

export function useCreateContactMutation() {
  return useMutation({
    mutationFn: createContactApi,
  });
}

export function useStarredContactsQuery() {
  return useQuery({
    queryKey: ['contacts-starred'],
    queryFn: fetchStarredContactsApi,
  });
}

export function useMergeContactsMutation() {
  return useMutation({
    mutationFn: mergeContactsApi,
  });
}

export function useImportContactsCsvMutation() {
  return useMutation({
    mutationFn: importContactsCsvApi,
  });
}

export function useBulkDeleteContactsMutation() {
  return useMutation({
    mutationFn: bulkDeleteContactsApi,
  });
}

export function useContactQuery(id: string) {
  return useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContactByIdApi(id),
    enabled: !!id,
  });
}

export function useUpdateContactMutation() {
  return useMutation({
    mutationFn: updateContactApi,
  });
}

export function useDeleteContactMutation() {
  return useMutation({
    mutationFn: deleteContactApi,
  });
}

export function useStarContactMutation() {
  return useMutation({
    mutationFn: starContactApi,
  });
}

export function useUnstarContactMutation() {
  return useMutation({
    mutationFn: unstarContactApi,
  });
}
