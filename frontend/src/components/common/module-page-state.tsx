'use client';

import { AlertCircle } from 'lucide-react';
import { useEffect } from 'react';

export function ModuleError({ message, retry }: { message: string; retry?: () => void }) {
  return <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><span className="flex items-center gap-2"><AlertCircle size={18}/>{message}</span>{retry && <button type="button" className="font-semibold underline" onClick={retry}>Try again</button>}</div>;
}

export function PageNavigator({ page, total, limit, onChange }: { page: number; total: number; limit: number; onChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / limit));
  useEffect(() => {
    if (page > pages) onChange(pages);
  }, [onChange, page, pages]);
  if (pages <= 1 && page <= 1) return null;
  return <nav aria-label="Pagination" className="flex items-center justify-between border-t bg-white p-4 text-sm"><span>Page {page} of {pages} · {total} records</span><div className="flex gap-2"><button type="button" className="rounded-lg border px-3 py-1.5 disabled:opacity-40" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button><button type="button" className="rounded-lg border px-3 py-1.5 disabled:opacity-40" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button></div></nav>;
}
