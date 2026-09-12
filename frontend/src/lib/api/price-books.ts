import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface PriceBook { id: string; name: string; currency: string; is_default: boolean; is_active: boolean; product_count: number; }
export interface PriceBookEntry { id: string; price_book_id: string; product_id: string; product_name: string; product_sku: string; unit_price: number; is_active: boolean; }
export interface PriceBookPayload { name: string; currency: string; is_default?: boolean; is_active?: boolean; }
export interface PriceBookContext { currency: string; }
export function usePriceBooks() { return useQuery({ queryKey: ['price-books'], queryFn: () => apiClient.get<PriceBook[]>('/price-books') }); }
export function usePriceBookContext() { return useQuery({ queryKey: ['price-books', 'context'], queryFn: () => apiClient.get<PriceBookContext>('/price-books/context') }); }
export function usePriceBookEntries(id: string) { return useQuery({ queryKey: ['price-books', id, 'entries'], queryFn: () => apiClient.get<PriceBookEntry[]>(`/price-books/${id}/entries`), enabled: Boolean(id) }); }
function useInvalidatePriceBooks() { const client = useQueryClient(); return () => client.invalidateQueries({ queryKey: ['price-books'] }); }
export function useCreatePriceBook() { const invalidate = useInvalidatePriceBooks(); return useMutation({ mutationFn: (payload: PriceBookPayload) => apiClient.post<PriceBook>('/price-books', payload), onSuccess: invalidate }); }
export function useUpdatePriceBook() { const invalidate = useInvalidatePriceBooks(); return useMutation({ mutationFn: ({ id, payload }: { id: string; payload: Partial<PriceBookPayload> }) => apiClient.put<PriceBook>(`/price-books/${id}`, payload), onSuccess: invalidate }); }
export function useDeletePriceBook() { const invalidate = useInvalidatePriceBooks(); return useMutation({ mutationFn: (id: string) => apiClient.delete(`/price-books/${id}`), onSuccess: invalidate }); }
export function useUpsertPriceBookEntry() { const invalidate = useInvalidatePriceBooks(); return useMutation({ mutationFn: ({ bookId, productId, unit_price }: { bookId: string; productId: string; unit_price: number }) => apiClient.put<{ message: string; status: string }>(`/price-books/${bookId}/entries/${productId}`, { unit_price, is_active: true }), onSuccess: invalidate }); }
export function useDeletePriceBookEntry() { const invalidate = useInvalidatePriceBooks(); return useMutation({ mutationFn: ({ bookId, productId }: { bookId: string; productId: string }) => apiClient.delete(`/price-books/${bookId}/entries/${productId}`), onSuccess: invalidate }); }
