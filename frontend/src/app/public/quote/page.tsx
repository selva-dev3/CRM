'use client';

import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, FileText, ShieldCheck, XCircle } from 'lucide-react';
import { publicQuoteApi, QuoteItem } from '@/lib/api/quotes';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type Decision = 'accept' | 'reject';
type PageState = 'loading' | 'ready' | 'accepting' | 'rejecting' | 'accepted' | 'rejected' | 'expired' | 'error';

function formatDate(value?: string | null) {
  if (!value) return 'Not specified';
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value));
}

function formatMoney(value: number | null | undefined, currency = 'USD') {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 2 }).format(Number(value ?? 0));
}

function isExpiredError(message: string) { return message.toLowerCase().includes('expired'); }

function stateForStatus(status: string): PageState {
  if (status === 'Accepted') return 'accepted';
  if (status === 'Rejected') return 'rejected';
  return 'ready';
}

export default function CustomerQuotePage() {
  const [quote, setQuote] = useState<QuoteItem | null>(null);
  const [pageState, setPageState] = useState<PageState>('loading');
  const [error, setError] = useState('');
  const [dialog, setDialog] = useState<Decision | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const token = useRef('');

  useEffect(() => {
    const capability = window.location.hash.slice(1) || sessionStorage.getItem('customer-quote-token') || '';
    token.current = capability;
    if (window.location.hash) {
      sessionStorage.setItem('customer-quote-token', capability);
      window.history.replaceState(null, '', window.location.pathname);
    }
    if (!capability) {
      queueMicrotask(() => {
        setError('Open the secure link from your quote email to continue.');
        setPageState('error');
      });
      return;
    }
    publicQuoteApi('view', capability).then((result) => {
      setQuote(result);
      setPageState(stateForStatus(result.status));
    }).catch((err) => {
      const message = err instanceof Error ? err.message : 'Unable to load this quote.';
      setError(message);
      setPageState(isExpiredError(message) ? 'expired' : 'error');
    });
  }, []);

  async function submitDecision() {
    if (!dialog || !token.current || pageState === 'accepting' || pageState === 'rejecting') return;
    const decision = dialog;
    setDialog(null);
    setError('');
    setPageState(decision === 'accept' ? 'accepting' : 'rejecting');
    try {
      const result = await publicQuoteApi(decision, token.current, rejectionReason);
      setQuote((current) => current ? { ...current, status: result.status } : current);
      setPageState(decision === 'accept' ? 'accepted' : 'rejected');
      setRejectionReason('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'The request could not be completed.';
      setError(message);
      setPageState(isExpiredError(message) ? 'expired' : 'ready');
    }
  }

  if (pageState === 'loading') return <main className="min-h-screen bg-slate-50 px-4 py-12"><div className="mx-auto max-w-4xl animate-pulse space-y-6"><div className="h-40 rounded-2xl bg-white shadow-sm" /><div className="h-64 rounded-2xl bg-white shadow-sm" /><div className="h-48 rounded-2xl bg-white shadow-sm" /></div></main>;

  if (pageState === 'error' || pageState === 'expired' || !quote) {
    const expired = pageState === 'expired';
    return <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 text-slate-950"><Card className="w-full max-w-lg"><CardContent className="space-y-4 p-8 text-center"><div className="mx-auto flex size-14 items-center justify-center rounded-full bg-amber-50 text-amber-600"><XCircle aria-hidden="true" className="size-7" /></div><h1 className="text-2xl font-semibold">{expired ? 'Quote expired' : 'Unable to open quote'}</h1><p className="text-slate-600">{expired ? 'This quote has expired. Please contact our team if you need a new quote.' : error}</p>{error && !expired && <p role="alert" className="text-sm text-rose-700">{error}</p>}</CardContent></Card></main>;
  }

  const currency = quote.currency || 'USD';
  const decisionInProgress = pageState === 'accepting' || pageState === 'rejecting';
  const canDecide = pageState === 'ready';
  const statusLabel = pageState === 'ready' || decisionInProgress ? 'Awaiting your approval' : pageState === 'accepted' ? 'Quote accepted' : 'Quote rejected';
  const statusVariant = pageState === 'accepted' ? 'success' : pageState === 'rejected' ? 'destructive' : 'warning';
  const subtotal = quote.items?.reduce((sum, item) => sum + Number(item.subtotal ?? item.total), 0) ?? 0;
  const discount = quote.items?.reduce((sum, item) => sum + Number(item.discount_total ?? 0), 0) ?? 0;
  const tax = quote.items?.reduce((sum, item) => sum + Number(item.tax_total ?? 0), 0) ?? 0;

  return <main className="min-h-screen bg-gradient-to-b from-slate-100 to-white px-4 py-8 text-slate-950 sm:py-14" aria-busy={decisionInProgress}><div className="mx-auto max-w-4xl space-y-6">
    <header className="rounded-2xl bg-slate-950 p-6 text-white shadow-xl sm:p-10"><div className="flex items-start justify-between gap-4"><div><div className="mb-6 flex items-center gap-3 text-sm font-medium text-slate-300"><span className="flex size-10 items-center justify-center rounded-xl bg-white/10"><FileText aria-hidden="true" className="size-5" /></span>Enterprise CRM</div><p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-300">Sales quote</p><h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">{quote.quote_number}</h1></div><Badge variant={statusVariant} className="shrink-0 px-3 py-1.5 text-xs">{statusLabel}</Badge></div><div className="mt-8 flex items-center gap-2 text-sm text-slate-300"><span>Valid until</span><span className="font-semibold text-white">{formatDate(quote.expires_at)}</span></div></header>
    <Card><CardHeader><CardTitle className="text-xl">Prepared for</CardTitle></CardHeader><CardContent className="grid gap-5 sm:grid-cols-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer</p><p className="mt-1 font-medium">{quote.contact_name || 'Not specified'}</p></div><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Company</p><p className="mt-1 font-medium">{quote.company_name || quote.client || 'Not specified'}</p></div><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email</p><p className="mt-1 break-words font-medium">{quote.contact_email || quote.recipient_email || 'Not specified'}</p></div></CardContent></Card>
    <Card><CardHeader><CardTitle className="text-xl">Quote details</CardTitle></CardHeader><CardContent className="space-y-6"><div className="overflow-x-auto"><Table className="min-w-[640px]"><TableCaption className="sr-only">Products and services included in this quote</TableCaption><TableHeader><TableRow><TableHead className="pl-0">Product / service</TableHead><TableHead className="text-right">Quantity</TableHead><TableHead className="text-right">Unit price</TableHead><TableHead className="pr-0 text-right">Total</TableHead></TableRow></TableHeader><TableBody>{quote.items?.length ? quote.items.map((item, index) => <TableRow key={`${item.product_name || item.name}-${index}`}><TableCell className="max-w-[260px] whitespace-normal pl-0 font-medium">{item.product_name || item.name || 'Product or service'}</TableCell><TableCell className="text-right tabular-nums">{item.quantity}</TableCell><TableCell className="text-right tabular-nums">{formatMoney(item.unit_price, currency)}</TableCell><TableCell className="pr-0 text-right font-semibold tabular-nums">{formatMoney(item.total, currency)}</TableCell></TableRow>) : <TableRow><TableCell colSpan={4} className="py-8 text-center text-slate-500">No line items are available.</TableCell></TableRow>}</TableBody></Table></div><div className="ml-auto max-w-sm space-y-3 text-sm"><div className="flex justify-between gap-6"><span className="text-slate-600">Subtotal</span><span className="tabular-nums">{formatMoney(subtotal, currency)}</span></div><div className="flex justify-between gap-6"><span className="text-slate-600">Discount</span><span className="tabular-nums">{formatMoney(discount, currency)}</span></div><div className="flex justify-between gap-6"><span className="text-slate-600">Tax</span><span className="tabular-nums">{formatMoney(tax, currency)}</span></div><Separator /><div className="flex justify-between gap-6 text-lg font-bold"><span>Total</span><span className="text-indigo-700 tabular-nums">{formatMoney(quote.total_amount, currency)}</span></div></div></CardContent></Card>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {pageState === 'accepted' && <Card className="border-emerald-200 bg-emerald-50/70"><CardContent className="flex gap-4 p-6"><CheckCircle2 aria-hidden="true" className="mt-0.5 size-6 shrink-0 text-emerald-600" /><div><h2 className="font-semibold text-emerald-950">Quote accepted</h2><p className="mt-1 text-sm text-emerald-900">Thank you for accepting this quote. Our team will handle the next steps separately.</p></div></CardContent></Card>}
    {pageState === 'rejected' && <Card className="border-slate-200 bg-slate-50"><CardContent className="flex gap-4 p-6"><XCircle aria-hidden="true" className="mt-0.5 size-6 shrink-0 text-slate-600" /><div><h2 className="font-semibold">Quote rejected</h2><p className="mt-1 text-sm text-slate-600">This quote has been rejected successfully. Please contact our team if you have any questions.</p></div></CardContent></Card>}
    {canDecide && <Card className="border-indigo-100 bg-indigo-50/50"><CardContent className="space-y-5 p-6 sm:p-8"><div className="flex gap-3"><ShieldCheck aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-indigo-700" /><p className="text-sm leading-6 text-slate-700">Please review the quote details before choosing an action. Your decision will be recorded securely.</p></div><div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><Button variant="outline" size="lg" onClick={() => setDialog('reject')}>Reject quote</Button><Button size="lg" onClick={() => setDialog('accept')}>Accept quote</Button></div></CardContent></Card>}
  </div>
  <AlertDialog open={dialog === 'accept'} onOpenChange={(open) => !open && setDialog(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Accept this quote?</AlertDialogTitle><AlertDialogDescription>Please confirm that you have reviewed the quote details and agree to the quoted products, pricing, and terms.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={(event) => { event.preventDefault(); void submitDecision(); }}>Accept quote</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  <AlertDialog open={dialog === 'reject'} onOpenChange={(open) => !open && setDialog(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Reject this quote?</AlertDialogTitle><AlertDialogDescription>Are you sure you want to reject this quote? You may optionally provide a reason for our team.</AlertDialogDescription></AlertDialogHeader><textarea aria-label="Rejection reason (optional)" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} maxLength={500} placeholder="Reason (optional)" className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200" /><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={(event) => { event.preventDefault(); void submitDecision(); }}>Reject quote</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  {decisionInProgress && <div className="sr-only" role="status">{pageState === 'accepting' ? 'Accepting quote' : 'Rejecting quote'}</div>}
  </main>;
}
