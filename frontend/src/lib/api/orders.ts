import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { fetchPaginated, type PaginatedResult } from '@/lib/api/pagination';

export type OrderStatus = 'Confirmed' | 'Fulfilled' | 'Cancelled';
export interface OrderItemLine { id: string; product_id?: string; product_name: string; quantity: number; unit_price: number; discount_percent: number; tax_percent: number; total: number; }
export interface OrderItem { id: string; quote_id: string; deal_id?: string; company_id?: string; contact_id?: string; order_number: string; status: OrderStatus; currency: string; subtotal: number; discount_total: number; tax_total: number; total: number; confirmed_at: string; fulfilled_at?: string; cancelled_at?: string; items: OrderItemLine[]; }
export function fetchOrders(params: { page?: number; limit?: number; status?: string; search?: string } = {}): Promise<PaginatedResult<OrderItem>> { const query = new URLSearchParams({ page: String(params.page ?? 1), limit: String(params.limit ?? 20) }); if (params.status) query.set('status', params.status); if (params.search) query.set('search', params.search); return fetchPaginated(`/orders?${query}`); }
export function useOrders(params: Parameters<typeof fetchOrders>[0]) { return useQuery({ queryKey: ['orders', params], queryFn: () => fetchOrders(params), placeholderData: (old) => old }); }
export function useOrder(id: string) { return useQuery({ queryKey: ['orders', id], queryFn: () => apiClient.get<OrderItem>(`/orders/${id}`), enabled: Boolean(id) }); }
export function useCreateOrderFromQuote() { const client = useQueryClient(); return useMutation({ mutationFn: (quoteId: string) => apiClient.post<OrderItem>(`/orders/from-quote/${quoteId}`), onSuccess: () => client.invalidateQueries({ queryKey: ['orders'] }) }); }
export function useUpdateOrderStatus() { const client = useQueryClient(); return useMutation({ mutationFn: ({ id, status }: { id: string; status: 'Fulfilled' | 'Cancelled' }) => apiClient.patch<OrderItem>(`/orders/${id}/status`, { status }), onSuccess: (order) => { client.setQueryData(['orders', order.id], order); client.invalidateQueries({ queryKey: ['orders'] }); } }); }
