'use client';

import { useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { ModalShell } from '@/components/common/modal-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ApiError } from '@/lib/api/client';
import { getErrorMessage } from '@/lib/utils';
import { manualPaymentSchema, paymentTypes, type ManualPaymentDto } from '@/lib/types/manual-payment';
import { useEligiblePaymentInvoicesQuery, useRecordInvoicePaymentMutation, type EligiblePaymentInvoice } from '@/lib/api/payments';

function money(value: number | string, currency: string) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value)); }
function today() { return new Date().toISOString().slice(0, 10); }

export function AddPaymentDialog() {
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState('');
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const submitting = useRef(false);
  const invoices = useEligiblePaymentInvoicesQuery({ enabled: open });
  const record = useRecordInvoicePaymentMutation();
  const form = useForm<ManualPaymentDto>({ resolver: zodResolver(manualPaymentSchema), defaultValues: { payment_type: 'Cash', amount: '', payment_date: today(), notes: '' } });
  const selected: EligiblePaymentInvoice | undefined = invoices.data?.find((invoice) => invoice.id === selectedId);

  function close() { if (!record.isPending) { setOpen(false); setError(''); } }
  function selectInvoice(value: string) { setSelectedId(value); form.clearErrors(); }

  async function submit(payment: ManualPaymentDto) {
    if (!selected || submitting.current || record.isPending) return;
    const key = idempotencyKey || crypto.randomUUID();
    setIdempotencyKey(key); submitting.current = true; setError('');
    try {
      await record.mutateAsync({ invoiceId: selected.id, payment, idempotencyKey: key });
      toast.success(`Payment recorded for ${selected.invoice_number}.`);
      setOpen(false); setSelectedId(''); setIdempotencyKey('');
      form.reset({ payment_type: 'Cash', amount: '', payment_date: today(), notes: '' });
    } catch (err) {
      const message = getErrorMessage(err, 'Unable to record payment.'); setError(message); form.setError('root', { message });
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) setIdempotencyKey('');
    } finally { submitting.current = false; }
  }

  return <>
    <Button onClick={() => setOpen(true)}>Add Payment</Button>
    <ModalShell isOpen={open} onClose={close} title="Add manual payment" size="2xl">
      <div className="space-y-5"><p className="text-sm text-slate-600">Record a payment received by your organization. The invoice balance is validated by the server before saving.</p>
        {invoices.isError && <Alert variant="destructive"><AlertDescription>{getErrorMessage(invoices.error, 'Unable to load eligible invoices.')}</AlertDescription></Alert>}
        <Form {...form}><form onSubmit={(event) => void form.handleSubmit(submit)(event)} className="space-y-4">
          <div><label htmlFor="payment-invoice" className="text-sm font-medium">Accepted invoice</label><select id="payment-invoice" value={selectedId} onChange={(event) => selectInvoice(event.target.value)} disabled={invoices.isLoading || record.isPending || Boolean(idempotencyKey)} className="mt-1 min-h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"><option value="">{invoices.isLoading ? 'Loading eligible invoices…' : invoices.data?.length ? 'Select an invoice' : 'No eligible invoices'}</option>{invoices.data?.map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} · {invoice.customer_name || invoice.contact_name || 'Customer'} · {money(invoice.outstanding_amount, invoice.currency)} outstanding</option>)}</select></div>
          {selected && <div className="grid gap-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 text-sm sm:grid-cols-3"><div><p className="text-xs text-slate-500">Invoice total</p><p className="font-semibold">{money(selected.amount, selected.currency)}</p></div><div><p className="text-xs text-slate-500">Paid amount</p><p className="font-semibold">{money(selected.paid_amount, selected.currency)}</p></div><div><p className="text-xs text-slate-500">Outstanding</p><p className="font-bold text-indigo-700">{money(selected.outstanding_amount, selected.currency)}</p></div></div>}
          <fieldset disabled={!selected || record.isPending || Boolean(idempotencyKey)} className="grid gap-4 sm:grid-cols-2"><FormField control={form.control} name="payment_type" render={({ field }) => <FormItem><FormLabel>Payment type</FormLabel><FormControl><select {...field} className="min-h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"><option value="">Select type</option>{paymentTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></FormControl><FormMessage /></FormItem>} /><FormField control={form.control} name="amount" render={({ field }) => <FormItem><FormLabel>Payment amount {selected && <span className="font-normal text-slate-500">(max {money(selected.outstanding_amount, selected.currency)})</span>}</FormLabel><FormControl><Input {...field} inputMode="decimal" placeholder="0.00" /></FormControl><FormMessage /></FormItem>} /><FormField control={form.control} name="payment_date" render={({ field }) => <FormItem><FormLabel>Payment date</FormLabel><FormControl><Input {...field} type="date" /></FormControl><FormMessage /></FormItem>} /><FormField control={form.control} name="notes" render={({ field }) => <FormItem><FormLabel>Notes (optional)</FormLabel><FormControl><Textarea {...field} placeholder="Reference or additional details" /></FormControl><FormMessage /></FormItem>} /></fieldset>
          {(error || form.formState.errors.root) && <Alert variant="destructive"><AlertDescription>{error || form.formState.errors.root?.message}</AlertDescription></Alert>}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button type="button" variant="outline" onClick={close} disabled={record.isPending}>Cancel</Button><Button type="submit" disabled={!selected || record.isPending}>{record.isPending ? 'Saving…' : idempotencyKey ? 'Retry same payment' : 'Save payment'}</Button></div>
        </form></Form>
      </div>
    </ModalShell>
  </>;
}
