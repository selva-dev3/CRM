'use client';

import { useEffect, useRef, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Loader2, MessageCircle, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Card, Form, FormControl, FormField, FormItem, FormLabel, FormMessage, Input } from '@/components/ui';
import { UserSelect } from '@/components/common/user-select';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useWhatsAppConfiguration, useWhatsAppStatus } from '@/lib/api/whatsapp';
import { PERMISSIONS } from '@/lib/permissions';
import { type WhatsAppConfigForm, whatsappConfigFormSchema } from '@/lib/types/whatsapp';
import { getErrorMessage } from '@/lib/utils';

export function WhatsAppIntegrationCard() {
  const { hasPermission } = useHasPermission();
  const canManage = hasPermission(PERMISSIONS.INTEGRATIONS.MANAGE);
  const status = useWhatsAppStatus(hasPermission(PERMISSIONS.INTEGRATIONS.READ) || canManage);
  const { configure, action } = useWhatsAppConfiguration();
  const [saving, setSaving] = useState(false);
  const hydratedConfiguration = useRef('');
  const form = useForm<WhatsAppConfigForm>({ resolver: zodResolver(whatsappConfigFormSchema), defaultValues: {
    business_account_id: '', phone_number_id: '', access_token: '', api_version: '',
    default_phone_region: '', ai_user_id: '', default_assignee_id: '',
  }});
  useEffect(() => {
    if (!status.data?.configured) return;
    const key = `${status.data.business_account_id}:${status.data.phone_number_id}:${status.data.api_version}`;
    if (hydratedConfiguration.current === key) return;
    hydratedConfiguration.current = key;
    form.reset({
      business_account_id: status.data.business_account_id ?? '',
      phone_number_id: status.data.phone_number_id ?? '',
      access_token: '',
      api_version: status.data.api_version ?? '',
      default_phone_region: status.data.default_phone_region ?? '',
      ai_user_id: status.data.ai_user_id ?? '',
      default_assignee_id: status.data.default_assignee_id ?? '',
    });
  }, [form, status.data]);
  const save = async (values: WhatsAppConfigForm) => {
    setSaving(true);
    try { await configure(values); form.reset({ ...values, access_token: '' }); toast.success('WhatsApp credentials saved. Verify the connection before enabling it.'); }
    catch (error) { form.setError('root', { message: getErrorMessage(error, 'Unable to save WhatsApp configuration.') }); }
    finally { setSaving(false); }
  };
  const run = async (operation: 'verify' | 'normalize-phones' | 'sync-templates' | 'disconnect') => {
    try { await action.mutateAsync(operation); toast.success(operation === 'disconnect' ? 'WhatsApp disconnected; history was retained.' : operation === 'verify' ? 'WhatsApp connection verified.' : 'Phone normalization batch completed.'); }
    catch (error) { toast.error(getErrorMessage(error, 'WhatsApp operation failed.')); }
  };
  if (status.isLoading) return <Card className="p-6"><Loader2 className="size-5 animate-spin" aria-label="Loading WhatsApp connection" /></Card>;
  if (status.isError) return <Card className="p-6 text-sm text-destructive" role="alert">{getErrorMessage(status.error, 'Unable to load WhatsApp connection.')}</Card>;
  const data = status.data;
  return <Card className="space-y-5 p-5 sm:p-6">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><h2 className="flex items-center gap-2 text-lg font-semibold"><MessageCircle className="size-5" />WhatsApp Connection</h2><p className="mt-1 text-sm text-muted-foreground">Meta Cloud API · credentials are write-only and encrypted by the backend.</p></div>
      <span className="w-fit rounded-full border px-3 py-1 text-xs font-medium">{data?.ready ? 'Ready' : data?.enabled ? 'Connected · setup incomplete' : data?.configured ? data.status : 'Disconnected'}</span>
    </div>
    {data?.configured && <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
      <div><dt className="text-muted-foreground">Business account</dt><dd>{data.business_account_id}</dd></div><div><dt className="text-muted-foreground">Phone</dt><dd>{data.masked_phone_number ?? 'Not verified'}</dd></div>
      <div><dt className="text-muted-foreground">Webhook</dt><dd>{data.webhook_status === 'OBSERVED' && data.last_webhook_at ? `Observed ${new Date(data.last_webhook_at).toLocaleString()}` : data.webhook_status === 'STALE' ? 'Last event is stale' : 'No verified event'}</dd></div><div><dt className="text-muted-foreground">Worker</dt><dd>{data.worker_status === 'HEALTHY' ? 'Healthy' : data.worker_status.toLowerCase()}</dd></div>
      <div><dt className="text-muted-foreground">AI service user</dt><dd>{data.ai_status === 'READY' ? 'Ready' : data.ai_status.toLowerCase().replaceAll('_', ' ')}</dd></div><div><dt className="text-muted-foreground">Phone index</dt><dd>{data.phone_index_ready ? 'Ready' : 'Normalization required'}</dd></div>
    </dl>}
    {data?.configured && <p className="text-sm text-muted-foreground">{data.backlog_age_seconds >= 300 ? 'Message processing is delayed. Ask an administrator to check the worker queue.' : 'Readiness reflects configuration and recent worker activity. Delivery and AI provider access still require a successful message test.'}</p>}
    {canManage && <Form {...form}><form onSubmit={form.handleSubmit(save)} className="space-y-4" autoComplete="off">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {(['business_account_id', 'phone_number_id', 'api_version', 'default_phone_region'] as const).map((name) => <FormField key={name} control={form.control} name={name} render={({ field }) => <FormItem><FormLabel>{name.replaceAll('_', ' ')}</FormLabel><FormControl><Input {...field} value={field.value ?? ''} autoComplete="off" /></FormControl><FormMessage /></FormItem>} />)}
        <FormField control={form.control} name="default_assignee_id" render={({ field }) => <FormItem><FormLabel>Default assignee</FormLabel><UserSelect value={field.value} onChange={field.onChange} /><FormMessage /></FormItem>} />
        <FormField control={form.control} name="ai_user_id" render={({ field }) => <FormItem><FormLabel>AI service user (optional)</FormLabel><UserSelect value={field.value} onChange={field.onChange} /><FormMessage /></FormItem>} />
      </div>
      <FormField control={form.control} name="access_token" render={({ field }) => <FormItem><FormLabel>Access token</FormLabel><FormControl><Input {...field} type="password" value={field.value ?? ''} autoComplete="new-password" /></FormControl><FormMessage /></FormItem>} />
      {form.formState.errors.root?.message && <p className="text-sm text-destructive" role="alert">{form.formState.errors.root.message}</p>}
      <div className="flex flex-wrap gap-2"><Button type="submit" disabled={saving || action.isPending}>{saving && <Loader2 className="mr-2 size-4 animate-spin" />}Save credentials</Button>
        {data?.configured && <Button type="button" variant="outline" disabled={saving || action.isPending} onClick={() => run('verify')}><ShieldCheck className="mr-2 size-4" />Verify</Button>}
        {data?.configured && !data.phone_index_ready && <Button type="button" variant="outline" disabled={action.isPending} onClick={() => run('normalize-phones')}>Normalize next batch</Button>}
        {data?.enabled && <Button type="button" variant="outline" disabled={action.isPending} onClick={() => run('sync-templates')}>Sync templates</Button>}
        {data?.configured && <Button type="button" variant="outline" disabled={action.isPending} onClick={() => run('disconnect')}>Disconnect</Button>}</div>
    </form></Form>}
  </Card>;
}
