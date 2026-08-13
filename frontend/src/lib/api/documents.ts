import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface DocumentItem {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  download_url: string;
  uploaded_at: string;
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

export async function fetchDocumentsApi(params?: { page?: number; limit?: number; folder_id?: string; search?: string }): Promise<DocumentItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.folder_id) query.append('folder_id', params.folder_id);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/documents${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<DocumentItem[]>(endpoint);
}

export async function uploadDocumentApi(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post<DocumentItem>('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
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

export function useDocumentsQuery(params?: { page?: number; limit?: number; folder_id?: string; search?: string }, options?: Omit<UseQueryOptions<DocumentItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<DocumentItem[]>({
    queryKey: ['documents', params],
    queryFn: () => fetchDocumentsApi(params),
    staleTime: 1000 * 60 * 2,
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
    mutationFn: uploadDocumentApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
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
