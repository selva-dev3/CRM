import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ProductItem {
  id: string;
  name: string;
  sku: string;
  price: number;
  category?: string;
  in_stock_quantity?: number;
}

export interface ProductCreatePayload {
  name: string;
  sku?: string;
  price: number;
  category?: string;
}

export interface PriceBookItem {
  id: string;
  name: string;
  currency: string;
  is_default: boolean;
}

export interface TaxRateItem {
  id: string;
  name: string;
  rate_percentage: number;
}

export interface InventoryResponse {
  product_id: string;
  in_stock_quantity: number;
  reorder_level: number;
  warehouse_location?: string;
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

export async function fetchProductsApi(params?: { page?: number; limit?: number; category?: string; search?: string }): Promise<ProductItem[]> {
  const query = new URLSearchParams();
  if (params?.page) query.append('page', String(params.page));
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.category) query.append('category', params.category);
  if (params?.search) query.append('search', params.search);
  const endpoint = `/products${query.toString() ? `?${query.toString()}` : ''}`;
  return apiClient.get<ProductItem[]>(endpoint);
}

export async function createProductApi(payload: ProductCreatePayload): Promise<ProductItem> {
  return apiClient.post<ProductItem>('/products', payload);
}

export async function fetchProductCategoriesApi(): Promise<string[]> {
  return apiClient.get<string[]>('/products/categories');
}

export async function createProductCategoryApi(name: string): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/products/categories?name=${encodeURIComponent(name)}`);
}

export async function fetchPriceBooksApi(): Promise<PriceBookItem[]> {
  return apiClient.get<PriceBookItem[]>('/products/price-books');
}

export async function createPriceBookApi(name: string, currency: string = 'USD'): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/products/price-books?name=${encodeURIComponent(name)}&currency=${encodeURIComponent(currency)}`);
}

export async function fetchTaxRatesApi(): Promise<TaxRateItem[]> {
  return apiClient.get<TaxRateItem[]>('/products/tax-rates');
}

export async function exportProductsCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/products/export/csv');
}

export async function importProductsCsvApi(): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>('/products/import/csv');
}

export async function bulkDeleteProductsApi(ids: string[]): Promise<BulkActionResponse> {
  return apiClient.post<BulkActionResponse>('/products/bulk-delete', { ids });
}

export async function fetchProductApi(productId: string): Promise<ProductItem> {
  return apiClient.get<ProductItem>(`/products/${productId}`);
}

export async function updateProductApi(productId: string, payload: ProductCreatePayload): Promise<ProductItem> {
  return apiClient.put<ProductItem>(`/products/${productId}`, payload);
}

export async function deleteProductApi(productId: string): Promise<MessageResponse> {
  return apiClient.delete<MessageResponse>(`/products/${productId}`);
}

export async function fetchProductInventoryApi(productId: string): Promise<InventoryResponse> {
  return apiClient.get<InventoryResponse>(`/products/${productId}/inventory`);
}

export async function updateProductInventoryApi(productId: string, quantityDelta: number): Promise<MessageResponse> {
  return apiClient.post<MessageResponse>(`/products/${productId}/inventory?quantity_delta=${quantityDelta}`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useProductsQuery(params?: { page?: number; limit?: number; category?: string; search?: string }, options?: Omit<UseQueryOptions<ProductItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<ProductItem[]>({
    queryKey: ['products', params],
    queryFn: () => fetchProductsApi(params),
    staleTime: 1000 * 60 * 2,
    ...options,
  });
}

export function useProductQuery(productId: string, options?: Omit<UseQueryOptions<ProductItem>, 'queryKey' | 'queryFn'>) {
  return useQuery<ProductItem>({
    queryKey: ['products', productId],
    queryFn: () => fetchProductApi(productId),
    enabled: !!productId,
    ...options,
  });
}

export function useProductCategoriesQuery(options?: Omit<UseQueryOptions<string[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<string[]>({
    queryKey: ['products', 'categories'],
    queryFn: fetchProductCategoriesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function usePriceBooksQuery(options?: Omit<UseQueryOptions<PriceBookItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<PriceBookItem[]>({
    queryKey: ['products', 'price-books'],
    queryFn: fetchPriceBooksApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useTaxRatesQuery(options?: Omit<UseQueryOptions<TaxRateItem[]>, 'queryKey' | 'queryFn'>) {
  return useQuery<TaxRateItem[]>({
    queryKey: ['products', 'tax-rates'],
    queryFn: fetchTaxRatesApi,
    staleTime: 1000 * 60 * 5,
    ...options,
  });
}

export function useProductInventoryQuery(productId: string, options?: Omit<UseQueryOptions<InventoryResponse>, 'queryKey' | 'queryFn'>) {
  return useQuery<InventoryResponse>({
    queryKey: ['products', productId, 'inventory'],
    queryFn: () => fetchProductInventoryApi(productId),
    enabled: !!productId,
    ...options,
  });
}

export function useCreateProductMutation(options?: UseMutationOptions<ProductItem, Error, ProductCreatePayload>) {
  const queryClient = useQueryClient();
  return useMutation<ProductItem, Error, ProductCreatePayload>({
    mutationFn: createProductApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    ...options,
  });
}

export function useUpdateProductMutation(options?: UseMutationOptions<ProductItem, Error, { id: string; payload: ProductCreatePayload }>) {
  const queryClient = useQueryClient();
  return useMutation<ProductItem, Error, { id: string; payload: ProductCreatePayload }>({
    mutationFn: ({ id, payload }) => updateProductApi(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['products', variables.id] });
    },
    ...options,
  });
}

export function useDeleteProductMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: deleteProductApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    ...options,
  });
}

export function useBulkDeleteProductsMutation(options?: UseMutationOptions<BulkActionResponse, Error, string[]>) {
  const queryClient = useQueryClient();
  return useMutation<BulkActionResponse, Error, string[]>({
    mutationFn: bulkDeleteProductsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    ...options,
  });
}

export function useCreateCategoryMutation(options?: UseMutationOptions<MessageResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, string>({
    mutationFn: createProductCategoryApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products', 'categories'] });
    },
    ...options,
  });
}

export function useCreatePriceBookMutation(options?: UseMutationOptions<MessageResponse, Error, { name: string; currency?: string }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { name: string; currency?: string }>({
    mutationFn: ({ name, currency }) => createPriceBookApi(name, currency),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products', 'price-books'] });
    },
    ...options,
  });
}

export function useImportProductsCsvMutation(options?: UseMutationOptions<MessageResponse, Error, void>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, void>({
    mutationFn: importProductsCsvApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    ...options,
  });
}

export function useUpdateProductInventoryMutation(options?: UseMutationOptions<MessageResponse, Error, { id: string; delta: number }>) {
  const queryClient = useQueryClient();
  return useMutation<MessageResponse, Error, { id: string; delta: number }>({
    mutationFn: ({ id, delta }) => updateProductInventoryApi(id, delta),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['products', variables.id, 'inventory'] });
    },
    ...options,
  });
}
