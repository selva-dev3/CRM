'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { publicQuoteApi, QuoteItem } from '@/lib/api/quotes';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export default function CustomerQuotePage() {
  const [quote, setQuote] = useState<QuoteItem | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [hasToken, setHasToken] = useState(false);
  const token = useRef('');
  const pending = useRef(false);

  const refresh = useCallback(async () => {
    setQuote(await publicQuoteApi('view', token.current));
  }, []);

  useEffect(() => {
    token.current = window.location.hash.slice(1) || sessionStorage.getItem('customer-quote-token') || '';
    if (window.location.hash) {
      sessionStorage.setItem('customer-quote-token', token.current);
      window.history.replaceState(null, '', window.location.pathname);
    }
    if (!token.current) {
      setError('Open the secure link in your quote email to continue.');
      setBusy(false);
      return;
    }
    setHasToken(true);
    refresh().catch(err => setError(err instanceof Error ? err.message : 'Unable to load quote.'))
      .finally(() => setBusy(false));
  }, [refresh]);

  async function act(action: 'accept' | 'reject' | 'checkout' | 'refresh') {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      if (action === 'checkout') {
        const result = await publicQuoteApi('checkout', token.current);
        const url = new URL(result.checkout_url);
        if (url.protocol !== 'https:' || url.hostname !== 'checkout.stripe.com') throw new Error('Invalid checkout URL.');
        window.location.assign(url.href);
      } else {
        if (action !== 'refresh') await publicQuoteApi(action, token.current);
        await refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The request failed. Please try again.');
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return <main className="min-h-screen bg-slate-50 px-4 py-12 text-slate-900">
    <section className="mx-auto max-w-3xl space-y-6 rounded-xl border bg-white p-6 sm:p-10" aria-busy={busy}>
      <h1 className="text-2xl font-semibold">Your sales quote</h1>
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-red-800">{error}</p>}
      {busy && <p role="status">Loading, please wait…</p>}
      {quote && <>
        <div><h2 className="font-semibold">{quote.quote_number}</h2><p>Status: {quote.status}</p>
          {quote.expires_at && <p>Valid until {new Date(quote.expires_at).toLocaleDateString()}</p>}</div>
        <div className="overflow-x-auto"><Table className="w-full text-left text-sm">
          <TableCaption className="sr-only">Quoted products and prices</TableCaption>
          <TableHeader><TableRow><TableHead className="py-3">Product / service</TableHead><TableHead>Quantity</TableHead><TableHead>Unit price</TableHead><TableHead>Total</TableHead></TableRow></TableHeader>
          <TableBody>{quote.items?.map((item, index) => <TableRow key={index} className="border-t">
            <TableCell className="py-3">{item.product_name || item.name}</TableCell><TableCell>{item.quantity}</TableCell>
            <TableCell>{Number(item.unit_price).toFixed(2)}</TableCell><TableCell>{Number(item.total).toFixed(2)}</TableCell>
          </TableRow>)}</TableBody></Table></div>
        <p className="text-xl font-semibold">Total: {quote.currency} {Number(quote.total_amount).toFixed(2)}</p>
        {quote.status === 'Sent' && <div className="space-y-3">
          <p>Accepting this quote confirms the listed items and total and automatically creates your invoice.</p>
          <div className="flex flex-wrap gap-3"><Button disabled={busy} onClick={() => act('accept')}>Accept quote</Button>
            <Button variant="outline" disabled={busy} onClick={() => act('reject')}>Reject quote</Button></div>
        </div>}
        {quote.invoice_id && <div className="space-y-3 rounded border p-4">
          <h2 className="font-semibold">Invoice {quote.invoice_number}</h2><p>Payment status: {quote.invoice_status}</p>
          {quote.invoice_status !== 'Paid' && <>
            <p>Payment is confirmed only after our server verifies it with Stripe. After returning from checkout, refresh the status.</p>
            <Button disabled={busy} onClick={() => act('checkout')}>Pay securely with Stripe</Button>
          </>}
        </div>}
      </>}
      {hasToken && <Button variant="outline" disabled={busy} onClick={() => act('refresh')}>Refresh status</Button>}
    </section>
  </main>;
}
