'use client';

import Link from 'next/link';
import { useState } from 'react';
import { ShoppingCart } from 'lucide-react';

import { ModuleError, PageNavigator } from '@/components/common/module-page-state';
import { useOrders } from '@/lib/api/orders';

const LIMIT = 20;

export default function OrdersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const orders = useOrders({ page, limit: LIMIT, search: search || undefined, status: status || undefined });
  return <div className="space-y-6 pb-12">
    <header><h1 className="flex items-center gap-2 text-2xl font-bold"><ShoppingCart className="text-indigo-600" />Orders</h1><p className="mt-1 text-sm text-slate-500">Immutable sales records created from accepted quotes.</p></header>
    <div className="flex flex-col gap-3 rounded-xl border bg-white p-4 sm:flex-row"><input aria-label="Search orders" className="h-10 flex-1 rounded-lg border px-3" placeholder="Search order number" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /><select aria-label="Filter orders by status" className="h-10 rounded-lg border px-3" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option><option>Confirmed</option><option>Fulfilled</option><option>Cancelled</option></select></div>
    {orders.isError && <ModuleError message="Orders could not be loaded." retry={() => orders.refetch()} />}
    <div className="overflow-x-auto rounded-xl border bg-white"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-4">Order</th><th className="p-4">Status</th><th className="p-4">Confirmed</th><th className="p-4">Total</th></tr></thead><tbody>{orders.data?.items.map((order) => <tr key={order.id} className="border-t hover:bg-slate-50"><td className="p-4"><Link className="font-semibold text-indigo-600" href={`/orders/${order.id}`}>{order.order_number}</Link></td><td className="p-4">{order.status}</td><td className="p-4">{order.confirmed_at.slice(0,10)}</td><td className="p-4 font-semibold">{order.currency} {order.total.toFixed(2)}</td></tr>)}</tbody></table>{orders.isLoading && <p className="p-8 text-center text-slate-500">Loading orders…</p>}{!orders.isLoading && !orders.isError && !orders.data?.items.length && <p className="p-8 text-center text-slate-500">No orders found. Orders are created when approved quotes are accepted.</p>}<PageNavigator page={page} total={orders.data?.total ?? 0} limit={LIMIT} onChange={setPage}/></div>
  </div>;
}
