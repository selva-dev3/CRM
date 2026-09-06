'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { InvoiceItemsTable } from './InvoiceItemsTable';
import { formatDate } from '@/lib/formatters/date';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { useAcceptPublicInvoiceMutation, usePublicInvoiceQuery } from '@/lib/api/public-invoices';
import { InvoiceSummary } from './InvoiceSummary';
import { getErrorMessage } from '@/lib/utils';

export function PublicInvoiceView() {
  const [token, setToken] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { const raw = window.location.hash.slice(1); queueMicrotask(() => setToken(raw)); }, []);
  const query = usePublicInvoiceQuery(token ?? '');
  const accept = useAcceptPublicInvoiceMutation(token ?? '');
  const invoice = query.data;
  const validToken = token !== null && /^[a-f0-9]{64}$/i.test(token);
  return <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-8">
    {token === null || (validToken && query.isLoading) ? <p role="status">Loading invoice…</p> : !validToken ? <p role="alert">Open the complete secure invoice link from your email.</p> : query.isError ? <div role="alert"><p>{getErrorMessage(query.error, 'Unable to open invoice.')}</p><Button onClick={() => void query.refetch()}>Retry</Button></div> : invoice ? <>
      <header className="space-y-2"><h1 className="text-2xl font-bold">Invoice {invoice.invoice_number}</h1><p>Status: {invoice.status === 'Finalized' ? 'Awaiting your approval' : invoice.status}</p><p>Payment status: {invoice.payment_status}</p><p>Due date: {formatDate(invoice.due_date, { fallback: 'Not specified' })}</p></header>
      <Card><CardContent className="space-y-6 pt-6">
        <InvoiceItemsTable items={invoice.items} currency={invoice.currency} />
        <InvoiceSummary invoice={invoice} />
        {invoice.pdf_url && /^https?:\/\//i.test(invoice.pdf_url) && <Button asChild variant="outline"><a href={invoice.pdf_url} target="_blank" rel="noopener noreferrer">Download PDF</a></Button>}
      </CardContent></Card>
      {invoice.status === 'Finalized' && !invoice.accepted_at && <Button disabled={accept.isPending || accept.isSuccess} onClick={() => setConfirm(true)}>Accept invoice</Button>}
      {(invoice.status === 'Accepted' || accept.isSuccess) && <p role="status">Invoice accepted. Contact the sender to arrange payment.</p>}
      {invoice.status === 'Cancelled' && <p>This invoice has been cancelled.</p>}
      {accept.isError && <p role="alert">{getErrorMessage(accept.error, 'Unable to accept invoice.')}</p>}
      <ConfirmModal isOpen={confirm} onClose={() => !accept.isPending && setConfirm(false)} title="Accept invoice?" description="Confirm that you have reviewed and accept the invoice details." confirmText="Confirm acceptance" variant="default" isLoading={accept.isPending} onConfirm={async () => {
        if (accept.isPending) return;
        try { await accept.mutateAsync(); setConfirm(false); } catch { setConfirm(false); }
      }} />
    </> : <p role="alert">Invoice is unavailable.</p>}
  </main>;
}
