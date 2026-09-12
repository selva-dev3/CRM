import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

export interface DocumentItem {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  download_url: string;
  uploaded_at: string;
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
  deal_id?: string;
  quote_id?: string;
  invoice_id?: string;
  payment_id?: string;
  project_id?: string;
}

export interface DocumentRelations {
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
  deal_id?: string;
  quote_id?: string;
  invoice_id?: string;
  payment_id?: string;
  project_id?: string;
}

export interface FetchDocumentsParams extends DocumentRelations {
  page?: number;
  limit?: number;
  folder_id?: string;
  search?: string;
  project_linked?: boolean;
}

export interface DocumentDownloadResponse {
  download_url: string;
  filename: string;
  expires_in: number;
}

export interface BulkActionResponse {
  affected_count: number;
  message: string;
}

export interface MessageResponse {
  message: string;
  status: string;
}

// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

export async function fetchDocumentsApi(params?: FetchDocumentsParams): Promise<PaginatedResult<DocumentItem>> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.folder_id) query.append('folder_id', params.folder_id);
  if (params?.search) query.append('search', params.search);
  if (params?.project_linked) query.append('project_linked', 'true');
  for (const field of ['lead_id', 'contact_id', 'company_id', 'deal_id', 'quote_id', 'invoice_id', 'payment_id', 'project_id'] as const) {
    if (params?.[field]) query.append(field, params[field]);
  }
  const endpoint = `/documents${query.toString() ? `?${query.toString()}` : ''}`;
  return fetchPaginated<DocumentItem>(endpoint);
}

export async function uploadDocumentApi(file: File, relations: DocumentRelations = {}): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  const query = new URLSearchParams();
  for (const [field, value] of Object.entries(relations)) {
    if (value) query.append(field, value);
  }
  const queryString = query.toString();
  return apiClient.post<DocumentItem>(
    `/documents/upload${queryString ? `?${queryString}` : ''}`,
    formData,
  );
}

export async function fetchDocumentApi(documentId: string): Promise<DocumentItem> {
  return apiClient.get<DocumentItem>(`/documents/${documentId}`);
}

export async function deleteDocumentApi(documentId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/documents/${documentId}`);
}

export async function downloadDocumentApi(documentId: string): Promise<DocumentDownloadResponse> {
  return apiClient.get<DocumentDownloadResponse>(`/documents/${documentId}/download`);
}

export async function bulkDeleteDocumentsApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/documents/bulk-delete', { ids });
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useDocumentsQuery(params?: FetchDocumentsParams, options?: Omit<UseQueryOptions<PaginatedResult<DocumentItem>>, 'queryKey' | 'queryFn'>) {
  return useQuery<PaginatedResult<DocumentItem>>({
    queryKey: ['documents', params],
    queryFn: () => fetchDocumentsApi(params),
    staleTime: 1000 * 60 * 2,
    placeholderData: (previousData) => previousData,
    ...options,
  });
}

export function useDocumentQuery(documentId: string, options?: Omit<UseQueryOptions<DocumentItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<DocumentItem>({
    queryKey: ['documents', documentId],
    queryFn: () => fetchDocumentApi(documentId),
    enabled: !!documentId,
    ...options,
  });
}

export function useDownloadDocumentQuery(documentId: string, options?: Omit<UseQueryOptions<DocumentDownloadResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<DocumentDownloadResponse>({
    queryKey: ['documents', documentId, 'download'],
    queryFn: () => downloadDocumentApi(documentId),
    enabled: !!documentId,
    ...options,
  });
}

export function useUploadDocumentMutation(options?: UseMutationOptions<DocumentItem, Error, File>) {
  const queryClient = useQueryClient();
  return useMutation<DocumentItem, Error, File>({
    mutationFn: (file) => uploadDocumentApi(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    ...options,
  });
}

export function useUploadRelatedDocumentMutation(
  options?: UseMutationOptions<DocumentItem, Error, { file: File; relations: DocumentRelations }>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, relations }) => uploadDocumentApi(file, relations),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
    ...options,
  });
}

export function useDeleteDocumentMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteDocumentApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    ...options,
  });
}

export function useBulkDeleteDocumentsMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteDocumentsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    ...options,
  });
}
