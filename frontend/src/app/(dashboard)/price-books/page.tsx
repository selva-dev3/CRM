'use client';

import { useState } from 'react';
import { BookOpen, Plus, Trash2 } from 'lucide-react';

import { ModuleError } from '@/components/common/module-page-state';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useProductsQuery } from '@/lib/api/products';
import { useCreatePriceBook, useDeletePriceBook, useDeletePriceBookEntry, usePriceBookEntries, usePriceBooks, useUpdatePriceBook, useUpsertPriceBookEntry } from '@/lib/api/price-books';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

export default function PriceBooksPage() {
  const { hasPermission } = useHasPermission();
  const [selected, setSelected] = useState('');
  const [name, setName] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [productId, setProductId] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [price, setPrice] = useState('');
  const [error, setError] = useState('');
  const books = usePriceBooks();
  const activeBookId = selected || books.data?.[0]?.id || '';
  const entries = usePriceBookEntries(activeBookId);
  const products = useProductsQuery({ page: 1, limit: 50, search: productSearch || undefined });
  const create = useCreatePriceBook();
  const update = useUpdatePriceBook();
  const remove = useDeletePriceBook();
  const upsert = useUpsertPriceBookEntry();
  const removeEntry = useDeletePriceBookEntry();

  async function runAction(action: () => Promise<unknown>, fallback: string) {
    try { await action(); setError(''); }
    catch (reason) { setError(getErrorMessage(reason, fallback)); }
  }

  async function addBook(event: React.FormEvent) {
    event.preventDefault();
    await runAction(async () => {
      const book = await create.mutateAsync({ name: name.trim(), currency, is_default: !books.data?.length });
      setSelected(book.id); setName('');
    }, 'Could not create price book.');
  }

  async function addEntry(event: React.FormEvent) {
    event.preventDefault();
    if (!activeBookId || !productId) return;
    await runAction(async () => {
      await upsert.mutateAsync({ bookId: activeBookId, productId, unit_price: Number(price) });
      setProductId(''); setPrice('');
    }, 'Could not save product price.');
  }

  return <div className="space-y-6 pb-12">
    <header><h1 className="flex items-center gap-2 text-2xl font-bold"><BookOpen className="text-indigo-600" />Price Books</h1><p className="mt-1 text-sm text-slate-500">Maintain reusable product pricing by currency.</p></header>
    {hasPermission(PERMISSIONS.PRODUCTS.CREATE) && <form onSubmit={addBook} className="flex flex-col gap-3 rounded-xl border bg-white p-4 sm:flex-row"><input required aria-label="Price book name" className="h-10 flex-1 rounded-lg border px-3" placeholder="Price book name" value={name} onChange={(event) => setName(event.target.value)} /><input required aria-label="Currency" maxLength={3} minLength={3} className="h-10 w-28 rounded-lg border px-3 uppercase" value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /><button disabled={create.isPending} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-white disabled:opacity-50"><Plus size={16} />{create.isPending ? 'Creating…' : 'Create'}</button></form>}
    {error && <ModuleError message={error}/>}
    {books.isError && <ModuleError message="Price books could not be loaded." retry={() => books.refetch()}/>}
    {entries.isError && <ModuleError message="Product prices could not be loaded." retry={() => entries.refetch()}/>}
    {products.isError && <ModuleError message="Products could not be loaded." retry={() => products.refetch()}/>}
    <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
      <aside className="max-h-[640px] overflow-y-auto rounded-xl border bg-white p-3"><h2 className="mb-3 font-bold">Books</h2>{books.data?.map((book) => <div key={book.id} className={`mb-2 rounded-lg border p-3 ${activeBookId === book.id ? 'border-indigo-500 bg-indigo-50' : ''}`}><button type="button" onClick={() => setSelected(book.id)} className="w-full text-left"><strong className="block">{book.name}</strong><small>{book.currency} · {book.product_count} products{book.is_default ? ' · Default' : ''}{!book.is_active ? ' · Inactive' : ''}</small></button>{hasPermission(PERMISSIONS.PRODUCTS.UPDATE) && <div className="mt-2 flex gap-3 text-xs font-semibold"><button disabled={update.isPending || book.is_default} onClick={() => runAction(() => update.mutateAsync({ id: book.id, payload: { is_default: true } }), 'Could not change default price book.')} className="text-indigo-600 disabled:opacity-40">Make default</button><button disabled={update.isPending} onClick={() => runAction(() => update.mutateAsync({ id: book.id, payload: { is_active: !book.is_active } }), 'Could not change price book status.')} className="text-slate-600">{book.is_active ? 'Disable' : 'Enable'}</button></div>}{hasPermission(PERMISSIONS.PRODUCTS.DELETE) && <button disabled={remove.isPending} aria-label={`Delete ${book.name}`} className="mt-2 text-rose-600 disabled:opacity-40" onClick={() => runAction(async () => { await remove.mutateAsync(book.id); if (activeBookId === book.id) setSelected(''); }, 'Could not delete price book.')}><Trash2 size={15}/></button>}</div>)}{books.isLoading && <p className="p-4 text-center text-sm text-slate-500">Loading price books…</p>}{!books.isLoading && !books.isError && !books.data?.length && <p className="p-4 text-center text-sm text-slate-500">No price books.</p>}</aside>
      <section className="rounded-xl border bg-white p-4"><h2 className="mb-4 font-bold">Product prices</h2>{activeBookId && hasPermission(PERMISSIONS.PRODUCTS.UPDATE) && <form onSubmit={addEntry} className="mb-4 grid gap-3 sm:grid-cols-2"><input aria-label="Search products" className="h-10 rounded-lg border px-3" placeholder="Search products…" value={productSearch} onChange={(event) => { setProductSearch(event.target.value); setProductId(''); }}/><select required aria-label="Product" className="h-10 rounded-lg border px-3" value={productId} onChange={(event) => setProductId(event.target.value)}><option value="">Select product</option>{products.data?.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>)}</select><input required min="0" step="0.01" type="number" aria-label="Unit price" className="h-10 rounded-lg border px-3" placeholder="Unit price" value={price} onChange={(event) => setPrice(event.target.value)}/><button disabled={upsert.isPending} className="rounded-lg bg-indigo-600 px-4 text-white disabled:opacity-50">{upsert.isPending ? 'Saving…' : 'Save price'}</button></form>}<div className="overflow-x-auto"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-3">Product</th><th className="p-3">SKU</th><th className="p-3">Unit price</th><th className="p-3">Actions</th></tr></thead><tbody>{entries.data?.map((entry) => <tr key={entry.id} className="border-t"><td className="p-3 font-semibold">{entry.product_name}</td><td className="p-3">{entry.product_sku}</td><td className="p-3">{entry.unit_price.toFixed(2)}</td><td className="p-3">{hasPermission(PERMISSIONS.PRODUCTS.UPDATE) && <button disabled={removeEntry.isPending} aria-label={`Remove ${entry.product_name}`} className="text-rose-600 disabled:opacity-40" onClick={() => runAction(() => removeEntry.mutateAsync({ bookId: activeBookId, productId: entry.product_id }), 'Could not remove product price.')}><Trash2 size={16}/></button>}</td></tr>)}</tbody></table>{entries.isLoading && <p className="p-8 text-center text-slate-500">Loading product prices…</p>}{activeBookId && !entries.isLoading && !entries.isError && !entries.data?.length && <p className="p-8 text-center text-slate-500">No product prices configured.</p>}</div></section>
    </div>
  </div>;
}
