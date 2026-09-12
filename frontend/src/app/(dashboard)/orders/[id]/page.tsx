'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ShoppingCart } from 'lucide-react';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';
import { useOrder, useUpdateOrderStatus } from '@/lib/api/orders';
import { ModuleError } from '@/components/common/module-page-state';
import { getErrorMessage } from '@/lib/utils';
import { useState } from 'react';

export default function OrderDetailPage() {
  const id = String(useParams().id ?? ''); const { hasPermission } = useHasPermission(); const order = useOrder(id); const update = useUpdateOrderStatus();
  const [error, setError] = useState('');
  async function updateStatus(status: 'Fulfilled' | 'Cancelled') { try { await update.mutateAsync({ id, status }); setError(''); } catch (reason) { setError(getErrorMessage(reason, 'Could not update order.')); } }
  if (order.isLoading) return <p className="p-8 text-slate-500">Loading order…</p>; if (order.isError || !order.data) return <ModuleError message="Order could not be loaded." retry={() => order.refetch()} />; const data = order.data;
  return <div className="space-y-6 pb-12"><Link href="/orders" className="inline-flex items-center gap-2 text-sm text-indigo-600"><ArrowLeft size={16}/>Back to orders</Link>{error && <ModuleError message={error}/>}<header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><h1 className="flex items-center gap-2 text-2xl font-bold"><ShoppingCart className="text-indigo-600"/>{data.order_number}</h1><p className="mt-1 text-sm text-slate-500">Created from quote {data.quote_id}</p></div>{hasPermission(PERMISSIONS.ORDERS.UPDATE) && data.status === 'Confirmed' && <div className="flex gap-2"><button disabled={update.isPending} onClick={() => updateStatus('Fulfilled')} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{update.isPending ? 'Updating…' : 'Mark fulfilled'}</button><button disabled={update.isPending} onClick={() => updateStatus('Cancelled')} className="rounded-lg border border-rose-300 px-4 py-2 font-semibold text-rose-700 disabled:opacity-50">Cancel order</button></div>}</header><div className="grid gap-4 sm:grid-cols-3"><div className="rounded-xl border bg-white p-4"><small className="uppercase text-slate-500">Status</small><strong className="mt-1 block">{data.status}</strong></div><div className="rounded-xl border bg-white p-4"><small className="uppercase text-slate-500">Confirmed</small><strong className="mt-1 block">{data.confirmed_at.slice(0,10)}</strong></div><div className="rounded-xl border bg-white p-4"><small className="uppercase text-slate-500">Total</small><strong className="mt-1 block">{data.currency} {data.total.toFixed(2)}</strong></div></div><div className="overflow-x-auto rounded-xl border bg-white"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-4">Product</th><th className="p-4">Quantity</th><th className="p-4">Unit price</th><th className="p-4">Total</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id} className="border-t"><td className="p-4 font-semibold">{item.product_name}</td><td className="p-4">{item.quantity}</td><td className="p-4">{data.currency} {item.unit_price.toFixed(2)}</td><td className="p-4">{data.currency} {item.total.toFixed(2)}</td></tr>)}</tbody></table></div></div>;
}
