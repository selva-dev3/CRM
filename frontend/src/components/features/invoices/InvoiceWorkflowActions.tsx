'use client';

import { useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { ModalShell } from '@/components/common/modal-shell';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';
import { ApiError } from '@/lib/api/client';
import {
  useFinalizeInvoiceMutation,
  useReturnInvoiceToDraftMutation,
  useSubmitInvoiceForReviewMutation,
  type InvoiceItem,
} from '@/lib/api/invoices';
import { useRecordInvoicePaymentMutation } from '@/lib/api/payments';
import { manualPaymentSchema, paymentTypes, type ManualPaymentDto } from '@/lib/types/manual-payment';
import { getErrorMessage } from '@/lib/utils';
import { useOptionalAuth } from '@/providers/auth-provider';
import { pendingPaymentKey, readPendingPayment, savePendingPayment, type PendingPayment } from '@/lib/api/pending-payment';

export function InvoiceWorkflowActions({ invoice }: { invoice: InvoiceItem }) {
  const { hasPermission } = useHasPermission();
  const auth = useOptionalAuth();
  const finalize = useFinalizeInvoiceMutation();
  const submitReview = useSubmitInvoiceForReviewMutation();
  const returnDraft = useReturnInvoiceToDraftMutation();
  const record = useRecordInvoicePaymentMutation();
  const [dialog, setDialog] = useState<'submit-review' | 'finalize' | 'return-draft' | 'payment' | null>(null);
  const [reviewReason, setReviewReason] = useState('');
  const [pending, setPending] = useState<PendingPayment | null>(null);
  const submitting = useRef(false);
  const form = useForm<ManualPaymentDto>({
    resolver: zodResolver(manualPaymentSchema),
    defaultValues: { payment_type: 'Cash', amount: '', payment_date: '', notes: '' },
  });
  const canRecord = invoice.status === 'Accepted' && Boolean(invoice.finalized_at && invoice.accepted_at) && invoice.payment_status !== 'Paid' && Number(invoice.outstanding_amount) > 0;
  const storageKey = auth?.user?.id ? pendingPaymentKey(auth.user.id, invoice.id) : null;

  function openPayment() {
    if (!storageKey) { toast.error('Sign in again before adding a payment.'); return; }
    try {
      const operation = readPendingPayment(storageKey);
      setPending(operation);
      if (operation) form.reset(operation.payment);
      setDialog('payment');
    } catch {
      toast.error('Unable to restore the pending payment. Check existing receipts before retrying; session storage must be available.');
    }
  }

  async function submit(payment: ManualPaymentDto) {
    if (submitting.current || !canRecord || !storageKey) return;
    if (!pending && Number(payment.amount) > Number(invoice.outstanding_amount)) {
      form.setError('amount', { message: 'Amount exceeds the outstanding balance.' });
      return;
    }
    submitting.current = true;
    try {
      // Store before sending. Until a definitive result, only this exact operation may be retried.
      const operation = readPendingPayment(storageKey) ?? { payment, idempotencyKey: crypto.randomUUID() };
      savePendingPayment(storageKey, operation);
      setPending(operation);
      await record.mutateAsync({ invoiceId: invoice.id, ...operation });
      sessionStorage.removeItem(storageKey);
      setPending(null);
      form.reset();
      setDialog(null);
      toast.success('Payment recorded.');
    } catch (error) {
      const rejectedPayment = error instanceof ApiError && error.status === 409 &&
        ['PAYMENT_EXCEEDS_BALANCE', 'INVOICE_ACCEPTANCE_REQUIRED'].includes(error.code ?? '');
      if (error instanceof ApiError && (error.status === 400 || error.status === 422 || rejectedPayment)) {
        sessionStorage.removeItem(storageKey);
        setPending(null);
      }
      if (error instanceof ApiError && error.fields) {
        for (const field of ['amount', 'payment_type', 'payment_date', 'notes'] as const) {
          const message = error.fields[field] ?? error.fields[`body.${field}`];
          if (typeof message === 'string') form.setError(field, { message });
        }
      }
      form.setError('root', { message: getErrorMessage(error, 'Unable to record payment. Retry with the same details.') });
      toast.error(getErrorMessage(error, 'Unable to record payment.'));
    } finally {
      submitting.current = false;
    }
  }

  return <>
    {invoice.status === 'Draft' && hasPermission(PERMISSIONS.INVOICES.UPDATE) && <Button onClick={() => setDialog('submit-review')}>Submit for review</Button>}
    {invoice.status === 'In Review' && hasPermission(PERMISSIONS.INVOICES.UPDATE) && <>
      <Button onClick={() => setDialog('finalize')}>Approve & finalize</Button>
      <Button variant="outline" onClick={() => setDialog('return-draft')}>Return to draft</Button>
    </>}
    {canRecord && hasPermission(PERMISSIONS.INVOICES.PAYMENT) && <Button onClick={openPayment}>Add Payment</Button>}
    <ConfirmModal isOpen={dialog === 'submit-review' || dialog === 'finalize'} onClose={() => !finalize.isPending && !submitReview.isPending && setDialog(null)} title={dialog === 'finalize' ? 'Approve and finalize invoice?' : 'Submit invoice for review?'} description={dialog === 'finalize' ? 'Finalizing locks the reviewed invoice for customer delivery and acceptance.' : 'The invoice will be locked while it is under review.'} confirmText={dialog === 'finalize' ? 'Approve & finalize' : 'Submit for review'} variant="default" isLoading={finalize.isPending || submitReview.isPending} onConfirm={async () => {
      if (finalize.isPending || submitReview.isPending) return;
      try {
        if (dialog === 'finalize') {
          await finalize.mutateAsync(invoice.id);
          toast.success('Invoice finalized.');
        } else {
          await submitReview.mutateAsync(invoice.id);
          toast.success('Invoice submitted for review.');
        }
        setDialog(null);
      }
      catch (error) { toast.error(getErrorMessage(error, 'Unable to update invoice review status.')); }
    }} />
    <ModalShell isOpen={dialog === 'return-draft'} onClose={() => !returnDraft.isPending && setDialog(null)} title="Return invoice to draft">
      <div className="space-y-4">
        <Textarea value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} placeholder="Required review feedback" maxLength={500} />
        <div className="flex gap-2"><Button type="button" variant="outline" onClick={() => setDialog(null)}>Cancel</Button><Button type="button" disabled={!reviewReason.trim() || returnDraft.isPending} onClick={async () => {
          try {
            await returnDraft.mutateAsync({ id: invoice.id, reason: reviewReason.trim() });
            setReviewReason('');
            setDialog(null);
            toast.success('Invoice returned to draft.');
          } catch (error) { toast.error(getErrorMessage(error, 'Unable to return invoice to draft.')); }
        }}>Return to draft</Button></div>
      </div>
    </ModalShell>
    <ModalShell isOpen={dialog === 'payment'} onClose={() => !record.isPending && setDialog(null)} title="Add Payment">
      <p className="mb-4 text-sm">Outstanding: {invoice.currency} {invoice.outstanding_amount}</p>
      {pending && <p role="status" className="mb-4 text-sm">A payment submission is awaiting confirmation. Retry the same payment to retrieve its result safely. The details are locked to prevent a duplicate payment, including after reloading this tab.</p>}
      <Form {...form}><form onSubmit={(event) => void form.handleSubmit(submit)(event)} className="space-y-4">
        <fieldset disabled={record.isPending || Boolean(pending)} className="space-y-4">
          <FormField control={form.control} name="payment_type" render={({ field }) => <FormItem><FormLabel>Payment type</FormLabel><FormControl><select {...field} className="min-h-11 w-full rounded-md border bg-background p-2">{paymentTypes.map(type => <option key={type}>{type}</option>)}</select></FormControl><FormMessage /></FormItem>} />
          <FormField control={form.control} name="amount" render={({ field }) => <FormItem><FormLabel>Amount</FormLabel><FormControl><Input {...field} inputMode="decimal" /></FormControl><FormMessage /></FormItem>} />
          <FormField control={form.control} name="payment_date" render={({ field }) => <FormItem><FormLabel>Payment date</FormLabel><FormControl><Input {...field} type="date" /></FormControl><FormMessage /></FormItem>} />
          <FormField control={form.control} name="notes" render={({ field }) => <FormItem><FormLabel>Notes (optional)</FormLabel><FormControl><Textarea {...field} /></FormControl><FormMessage /></FormItem>} />
        </fieldset>
        {form.formState.errors.root && <p role="alert" className="text-sm text-destructive">{form.formState.errors.root.message}</p>}
        <div className="flex flex-col gap-2 sm:flex-row"><Button type="button" variant="outline" disabled={record.isPending} onClick={() => setDialog(null)}>Cancel</Button><Button type="submit" disabled={record.isPending || !canRecord}>{record.isPending ? 'Saving…' : pending ? 'Retry same payment' : 'Add Payment'}</Button></div>
      </form></Form>
    </ModalShell>
  </>;
}
