'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2, Pencil, PhoneCall, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { ModalShell } from '@/components/common/modal-shell';
import { DateTimePicker } from '@/components/common/date-picker';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { PermissionGate } from '@/components/common/permission-gate';
import { ResponsiveSelect } from '@/components/common/responsive-select';
import { Alert, AlertDescription, Button, Card, Input, Label } from '@/components/ui';
import { Textarea } from '@/components/ui/textarea';
import {
  deleteLeadCallApi,
  logLeadCallApi,
  updateLeadCallApi,
  type LeadCallLogItem,
} from '@/lib/api/leads';
import { formatDateTime } from '@/lib/formatters/date';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const callFormSchema = z
  .object({
    call_type: z.enum(['Outbound', 'Inbound']),
    disposition: z.enum(['Completed', 'No Answer', 'Busy', 'Failed', 'Other']),
    timestamp: z.string().min(1, 'Call date and time are required.'),
    duration_seconds: z
      .number({ invalid_type_error: 'Duration must be a whole number.' })
      .int('Duration must be a whole number.')
      .min(0, 'Duration cannot be negative.')
      .max(86400, 'Duration cannot exceed 24 hours.'),
    subject: z.string().trim().max(255, 'Subject must be 255 characters or fewer.'),
    notes: z.string().trim().max(10000, 'Notes must be 10,000 characters or fewer.'),
    follow_up_required: z.boolean(),
    follow_up_at: z.string(),
    next_action: z.string().trim().max(1000, 'Next action must be 1,000 characters or fewer.'),
  })
  .superRefine((value, context) => {
    if (Number.isNaN(new Date(value.timestamp).getTime())) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ['timestamp'], message: 'Enter a valid call date and time.' });
    }
    if (value.follow_up_required && !value.follow_up_at) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ['follow_up_at'], message: 'Follow-up date and time are required.' });
    } else if (value.follow_up_at && Number.isNaN(new Date(value.follow_up_at).getTime())) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ['follow_up_at'], message: 'Enter a valid follow-up date and time.' });
    }
  });

type CallFormValues = z.infer<typeof callFormSchema>;

interface LeadCallLogSectionProps {
  leadId: string;
  leadContactName: string;
  relatedContactId?: string | null;
  relatedCompanyId?: string | null;
  relatedDealId?: string | null;
  calls: LeadCallLogItem[];
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  onRetry: () => void;
  timeZone: string;
}

function currentLocalDateTime(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toLocalDateTime(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function defaultValues(): CallFormValues {
  return {
    call_type: 'Outbound',
    disposition: 'Completed',
    timestamp: currentLocalDateTime(),
    duration_seconds: 0,
    subject: '',
    notes: '',
    follow_up_required: false,
    follow_up_at: '',
    next_action: '',
  };
}

export function LeadCallLogSection({
  leadId,
  leadContactName,
  relatedContactId,
  relatedCompanyId,
  relatedDealId,
  calls,
  isLoading,
  isError,
  error,
  onRetry,
  timeZone,
}: LeadCallLogSectionProps): React.JSX.Element {
  const queryClient = useQueryClient();
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingCall, setEditingCall] = useState<LeadCallLogItem | null>(null);
  const [deletingCall, setDeletingCall] = useState<LeadCallLogItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const form = useForm<CallFormValues>({
    resolver: zodResolver(callFormSchema),
    defaultValues: defaultValues(),
  });
  const followUpRequired = useWatch({ control: form.control, name: 'follow_up_required' });
  const columns = useMemo<readonly DataTableColumn<LeadCallLogItem>[]>(() => [
    {
      id: 'call',
      header: 'Call',
      cell: (call) => (
        <div className="font-bold text-slate-900">
          <p>{call.subject || `${call.call_type ?? 'Outbound'} Call`}</p>
          <p className="text-[10px] font-medium text-slate-500">{call.call_type}</p>
        </div>
      ),
    },
    { id: 'outcome', header: 'Outcome', cell: (call) => call.disposition || 'Not recorded' },
    { id: 'duration', header: 'Duration', cell: (call) => `${Math.floor((call.duration_seconds ?? 0) / 60)}m ${(call.duration_seconds ?? 0) % 60}s` },
    { id: 'summary', header: 'Summary', cell: (call) => call.notes || 'No notes', className: 'max-w-64 whitespace-normal' },
    { id: 'contact', header: 'Contact', cell: () => leadContactName },
    { id: 'timestamp', header: 'Date & Time', cell: (call) => call.timestamp ? formatDateTime(call.timestamp, { timeZone }) : 'Unknown' },
    { id: 'creator', header: 'Created By', cell: (call) => call.created_by_name || 'Legacy record' },
    {
      id: 'follow-up',
      header: 'Follow-up',
      cell: (call) => (
        <div>
          {call.follow_up_required
            ? call.follow_up_at ? formatDateTime(call.follow_up_at, { timeZone }) : 'Required'
            : 'None'}
          {call.next_action && <p className="mt-1 text-[10px] text-slate-500">{call.next_action}</p>}
        </div>
      ),
    },
  ], [leadContactName, timeZone]);

  const refreshCallViews = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['lead-calls', leadId] }),
      queryClient.invalidateQueries({ queryKey: ['lead-timeline', leadId] }),
      queryClient.invalidateQueries({ queryKey: ['calls'] }),
    ]);
  };

  const openCreate = (): void => {
    setEditingCall(null);
    setIdempotencyKey(null);
    form.reset(defaultValues());
    setMessage(null);
    setIsFormOpen(true);
  };

  const openEdit = (call: LeadCallLogItem): void => {
    setEditingCall(call);
    form.reset({
      call_type: call.call_type ?? 'Outbound',
      disposition: call.disposition ?? 'Completed',
      timestamp: toLocalDateTime(call.timestamp),
      duration_seconds: call.duration_seconds ?? 0,
      subject: call.subject ?? '',
      notes: call.notes ?? '',
      follow_up_required: call.follow_up_required ?? false,
      follow_up_at: toLocalDateTime(call.follow_up_at),
      next_action: call.next_action ?? '',
    });
    setMessage(null);
    setIsFormOpen(true);
  };

  const openDelete = (call: LeadCallLogItem): void => {
    setMessage(null);
    setDeletingCall(call);
  };

  const submitCall = form.handleSubmit(async (values) => {
    setMessage(null);
    const callDetails = {
      call_type: values.call_type,
      disposition: values.disposition,
      timestamp: new Date(values.timestamp).toISOString(),
      duration_seconds: values.duration_seconds,
      subject: values.subject || undefined,
      notes: values.notes || undefined,
      follow_up_required: values.follow_up_required,
      follow_up_at: values.follow_up_required ? new Date(values.follow_up_at).toISOString() : null,
      next_action: values.next_action || undefined,
    };
    try {
      if (editingCall) {
        await updateLeadCallApi(editingCall.id, callDetails);
      } else {
        const requestKey = idempotencyKey ?? crypto.randomUUID();
        setIdempotencyKey(requestKey);
        await logLeadCallApi(
          leadId,
          {
            ...callDetails,
            contact_id: relatedContactId || undefined,
            company_id: relatedCompanyId || undefined,
            deal_id: relatedDealId || undefined,
          },
          requestKey,
        );
        setIdempotencyKey(null);
      }
      await refreshCallViews();
      setIsFormOpen(false);
      setEditingCall(null);
      form.reset(defaultValues());
      setMessage({ kind: 'success', text: editingCall ? 'Call log updated.' : 'Call logged.' });
    } catch (error: unknown) {
      setMessage({ kind: 'error', text: getErrorMessage(error, `Failed to ${editingCall ? 'update' : 'log'} call.`) });
    }
  });

  const deleteCall = async (): Promise<void> => {
    if (!deletingCall || isDeleting) return;
    try {
      setIsDeleting(true);
      setMessage(null);
      await deleteLeadCallApi(deletingCall.id);
      await refreshCallViews();
      setDeletingCall(null);
      setMessage({ kind: 'success', text: 'Call log deleted.' });
    } catch (error: unknown) {
      setMessage({ kind: 'error', text: getErrorMessage(error, 'Failed to delete call.') });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Card className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      <div className="flex flex-col gap-4 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-wider text-slate-900">
            <PhoneCall className="size-4 text-indigo-600" /> Phone Call Logs ({calls.length})
          </h3>
          <p className="mt-0.5 text-xs font-bold text-slate-500">Manual call history for {leadContactName}</p>
        </div>
        <PermissionGate permission={PERMISSIONS.CALLS.CREATE}>
          <Button type="button" onClick={openCreate} className="h-9 cursor-pointer bg-indigo-600 px-4 text-xs font-bold text-white hover:bg-indigo-700">
            <Plus className="mr-1.5 size-3.5" /> Log Call
          </Button>
        </PermissionGate>
      </div>

      {message && !isFormOpen && !deletingCall && (
        <Alert variant={message.kind === 'error' ? 'destructive' : 'default'}>
          <AlertDescription>{message.text}</AlertDescription>
        </Alert>
      )}

      {isError ? (
        <Alert variant="destructive">
          <AlertDescription className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <span>{getErrorMessage(error, 'Call logs could not be loaded.')}</span>
            <Button type="button" variant="outline" size="sm" onClick={onRetry}>Retry</Button>
          </AlertDescription>
        </Alert>
      ) : (
        <DataTable
          columns={columns}
          data={calls}
          getRowKey={(call) => call.id}
          emptyTitle="No call logs recorded yet"
          emptyDescription="Use Log Call to record a phone conversation."
          isLoading={isLoading}
          tableClassName="min-w-[900px]"
          className="shadow-none"
          actionVariant="inline"
          actionColumnClassName="w-[180px]"
          pagination={{ pageSize: 15 }}
          actions={(call) => [
            { id: 'edit', label: 'Edit', ariaLabel: `Edit ${call.subject || 'call log'}`, icon: <Pencil className="size-3.5" />, permission: PERMISSIONS.CALLS.UPDATE, onClick: openEdit },
            { id: 'delete', label: 'Delete', ariaLabel: `Delete ${call.subject || 'call log'}`, icon: <Trash2 className="size-3.5" />, permission: PERMISSIONS.CALLS.DELETE, variant: 'destructive', onClick: openDelete },
          ]}
        />
      )}

      <ModalShell
        isOpen={isFormOpen}
        onClose={() => !form.formState.isSubmitting && setIsFormOpen(false)}
        size="2xl"
        ariaLabel={editingCall ? 'Edit call log' : 'Log phone call'}
        title={<h3 className="text-base font-black text-black">{editingCall ? 'Edit Call Log' : 'Log Phone Call'}</h3>}
      >
        <form noValidate onSubmit={submitCall} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {message?.kind === 'error' && (
            <Alert variant="destructive" className="sm:col-span-2" aria-live="polite">
              <AlertDescription>{message.text}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-1.5"><Label htmlFor="call-type">Call Type</Label><Controller name="call_type" control={form.control} render={({ field }) => <ResponsiveSelect id="call-type" value={field.value} onValueChange={field.onChange}><option value="Outbound">Outbound</option><option value="Inbound">Inbound</option></ResponsiveSelect>} /></div>
          <div className="space-y-1.5"><Label htmlFor="call-outcome">Status / Outcome</Label><Controller name="disposition" control={form.control} render={({ field }) => <ResponsiveSelect id="call-outcome" value={field.value} onValueChange={field.onChange}><option>Completed</option><option>No Answer</option><option>Busy</option><option>Failed</option><option>Other</option></ResponsiveSelect>} /></div>
          <div className="space-y-1.5"><Label htmlFor="call-timestamp">Call Date / Time *</Label><Controller name="timestamp" control={form.control} render={({ field }) => <DateTimePicker triggerRef={field.ref} id="call-timestamp" required aria-describedby={form.formState.errors.timestamp ? 'call-timestamp-error' : undefined} aria-invalid={Boolean(form.formState.errors.timestamp)} value={field.value} onValueChange={field.onChange} />} /><p id="call-timestamp-error" className="text-xs text-rose-600">{form.formState.errors.timestamp?.message}</p></div>
          <div className="space-y-1.5"><Label htmlFor="call-duration">Duration (seconds) *</Label><Input id="call-duration" type="number" min={0} max={86400} step={1} required aria-invalid={Boolean(form.formState.errors.duration_seconds)} aria-describedby={form.formState.errors.duration_seconds ? 'call-duration-error' : undefined} {...form.register('duration_seconds', { valueAsNumber: true })} />{form.formState.errors.duration_seconds && <p id="call-duration-error" className="text-xs text-rose-600">{form.formState.errors.duration_seconds.message}</p>}</div>
          <div className="space-y-1.5"><Label>Contact / Person</Label><div className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-bold">{leadContactName}</div></div>
          <div className="space-y-1.5"><Label htmlFor="call-subject">Subject / Title</Label><Input id="call-subject" maxLength={255} {...form.register('subject')} /><p className="text-xs text-rose-600">{form.formState.errors.subject?.message}</p></div>
          <div className="space-y-1.5 sm:col-span-2"><Label htmlFor="call-notes">Notes / Conversation Summary</Label><Textarea id="call-notes" rows={4} maxLength={10000} {...form.register('notes')} /><p className="text-xs text-rose-600">{form.formState.errors.notes?.message}</p></div>
          <label className="flex items-center gap-2 text-xs font-bold text-slate-800"><input type="checkbox" className="size-4" {...form.register('follow_up_required')} /> Follow-up required</label>
          {followUpRequired && <div className="space-y-1.5"><Label htmlFor="call-follow-up">Follow-up Date / Time *</Label><Controller name="follow_up_at" control={form.control} render={({ field }) => <DateTimePicker triggerRef={field.ref} id="call-follow-up" required aria-describedby={form.formState.errors.follow_up_at ? 'call-follow-up-error' : undefined} aria-invalid={Boolean(form.formState.errors.follow_up_at)} value={field.value} onValueChange={field.onChange} />} /><p id="call-follow-up-error" className="text-xs text-rose-600">{form.formState.errors.follow_up_at?.message}</p></div>}
          <div className="space-y-1.5 sm:col-span-2"><Label htmlFor="call-next-action">Next Action</Label><Input id="call-next-action" maxLength={1000} {...form.register('next_action')} /><p className="text-xs text-rose-600">{form.formState.errors.next_action?.message}</p></div>
          <div className="flex flex-col-reverse gap-2 border-t border-slate-100 pt-3 sm:col-span-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => setIsFormOpen(false)} disabled={form.formState.isSubmitting}>Cancel</Button>
            <Button type="submit" disabled={form.formState.isSubmitting} className="bg-indigo-600 text-white hover:bg-indigo-700">
              {form.formState.isSubmitting && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}{editingCall ? 'Save Changes' : 'Log Call'}
            </Button>
          </div>
        </form>
      </ModalShell>

      <ModalShell isOpen={Boolean(deletingCall)} onClose={() => !isDeleting && setDeletingCall(null)} ariaLabel="Delete call log" title="Delete Call Log">
        <p className="text-sm text-slate-700">Delete this call log? It will also disappear from the Lead timeline.</p>
        {message?.kind === 'error' && (
          <Alert variant="destructive" className="mt-4" aria-live="polite">
            <AlertDescription>{message.text}</AlertDescription>
          </Alert>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => setDeletingCall(null)} disabled={isDeleting}>Cancel</Button>
          <Button type="button" onClick={() => void deleteCall()} disabled={isDeleting} className="bg-rose-600 text-white hover:bg-rose-700">{isDeleting && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}Delete</Button>
        </div>
      </ModalShell>
    </Card>
  );
}
