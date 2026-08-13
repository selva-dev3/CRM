import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface NoteItem {
  id: string;
  entity_type: string;
  entity_id: string;
  content: string;
  is_pinned?: boolean;
  created_by?: string;
  created_at: string;
}

export interface NoteCreatePayload {
  entity_type?: string;
  entity_id?: string;
  content: string;
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

export async function fetchNotesApi(params?: { page?: number; limit?: number; entity_type?: string; search?: string }): Promise<NoteItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.entity_type) query.append('entity_type', params.entity_type);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/notes${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<NoteItem[]>(endpoint);
}

export async function createNoteApi(payload: NoteCreatePayload): Promise<NoteItem> {
  return apiClient.post<NoteItem>('/notes', payload);
}

export async function fetchPinnedNotesApi(): Promise<NoteItem[]> {
  return apiClient.get<NoteItem[]>('/notes/pinned');
}

export async function fetchNotesByEntityApi(entityType: string, entityId: string): Promise<NoteItem[]> {
  return apiClient.get<NoteItem[]>(`/notes/entity/${entityType}/${entityId}`);
}

export async function bulkDeleteNotesApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/notes/bulk-delete', { ids });
}

export async function fetchNoteApi(noteId: string): Promise<NoteItem> {
  return apiClient.get<NoteItem>(`/notes/${noteId}`);
}

export async function updateNoteApi(noteId: string, content: string): Promise<NoteItem> {
  return apiClient.put<NoteItem>(`/notes/${noteId}?content=${encodeURIComponent(content)}`);
}

export async function deleteNoteApi(noteId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/notes/${noteId}`);
}

export async function pinNoteApi(noteId: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/notes/${noteId}/pin`);
}

export async function unpinNoteApi(noteId: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/notes/${noteId}/unpin`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useNotesQuery(params?: { page?: number; limit?: number; entity_type?: string; search?: string }, options?: Omit<UseQueryOptions<NoteItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<NoteItem[]>({
    queryKey: ['notes', params],
    queryFn: () => fetchNotesApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useNoteQuery(noteId: string, options?: Omit<UseQueryOptions<NoteItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<NoteItem>({
    queryKey: ['notes', noteId],
    queryFn: () => fetchNoteApi(noteId),
    enabled: !!noteId,
    ...options,
  });
}

export function usePinnedNotesQuery(options?: Omit<UseQueryOptions<NoteItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<NoteItem[]>({
    queryKey: ['notes', 'pinned'],
    queryFn: fetchPinnedNotesApi,
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useNotesByEntityQuery(entityType: string, entityId: string, options?: Omit<UseQueryOptions<NoteItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<NoteItem[]>({
    queryKey: ['notes', 'entity', entityType, entityId],
    queryFn: () => fetchNotesByEntityApi(entityType, entityId),
    enabled: !!entityType && !!entityId,
    ...options,
  });
}

export function useCreateNoteMutation(options?: UseMutationOptions<NoteItem, Error, NoteCreatePayload>) {
  const queryClient = useQueryClient();
  return useMutation<NoteItem, Error, NoteCreatePayload>({
    mutationFn: createNoteApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    ...options,
  });
}

export function useUpdateNoteMutation(options?: UseMutationOptions<NoteItem, Error, { id: string; content: string }>) {
  const queryClient = useQueryClient();
  return useMutation<NoteItem, Error, { id: string; content: string }>({
    mutationFn: ({ id, content }) => updateNoteApi(id, content),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['notes', variables.id] });
    },
    ...options,
  });
}

export function useDeleteNoteMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteNoteApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    ...options,
  });
}

export function useBulkDeleteNotesMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteNotesApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    ...options,
  });
}

export function usePinNoteMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: pinNoteApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    ...options,
  });
}

export function useUnpinNoteMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: unpinNoteApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    ...options,
  });
}
