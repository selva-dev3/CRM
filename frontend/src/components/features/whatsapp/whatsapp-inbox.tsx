'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Bot, Loader2, MessageCircle, Send, UserRound } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { Button, Card, Form, FormControl, FormField, FormItem, FormMessage, Input, Textarea } from '@/components/ui';
import { useHasPermission } from '@/hooks/use-has-permission';
import { BASE_URL } from '@/lib/api/client';
import { useWhatsAppAssignees, useWhatsAppConversation, useWhatsAppConversationAction, useWhatsAppConversations, useWhatsAppIdentityAction, useWhatsAppLiveUpdates, useWhatsAppMessages, useWhatsAppRetryMessage, useWhatsAppScope, useWhatsAppSend, useWhatsAppSendTemplate, useWhatsAppTemplates } from '@/lib/api/whatsapp';
import { PERMISSIONS } from '@/lib/permissions';
import { type WhatsAppConversationDto, whatsappMessageFormSchema } from '@/lib/types/whatsapp';
import { getErrorMessage } from '@/lib/utils';

export function WhatsAppInbox() {
  const router = useRouter();
  const params = useSearchParams();
  const { hasAnyPermission, hasPermission } = useHasPermission();
  const selected = params.get('conversation') ?? '';
  const scope = useWhatsAppScope();
  const requestScope = `${scope}:${selected}`;
  const [search, setSearch] = useState(params.get('search') ?? '');
  const [conversationOffset, setConversationOffset] = useState(0);
  const [messageOffset, setMessageOffset] = useState(0);
  const [templateDrafts, setTemplateDrafts] = useState<Record<string, { templateId: string; parameters: string }>>({});
  const [resolutionType, setResolutionType] = useState<'contact' | 'lead'>('contact');
  const [resolutionId, setResolutionId] = useState('');
  const [currentTime, setCurrentTime] = useState(0);
  const canRead = hasAnyPermission([PERMISSIONS.WHATSAPP.READ_ALL, PERMISSIONS.WHATSAPP.READ_ASSIGNED]);
  const realtime = useWhatsAppLiveUpdates(selected, canRead);
  const list = useWhatsAppConversations(search, conversationOffset, canRead, realtime);
  const detail = useWhatsAppConversation(selected, canRead, realtime);
  const messages = useWhatsAppMessages(selected, messageOffset, canRead, realtime);
  const send = useWhatsAppSend(selected);
  const sendTemplate = useWhatsAppSendTemplate(selected);
  const retryMessage = useWhatsAppRetryMessage(selected);
  const action = useWhatsAppConversationAction(selected);
  const identityAction = useWhatsAppIdentityAction(selected, detail.data?.identity_id ?? '');
  const customerTime = detail.data?.last_customer_message_at ? new Date(detail.data.last_customer_message_at).getTime() : 0;
  const windowOpen = customerTime > 0 && currentTime >= customerTime && currentTime - customerTime < 86_400_000;
  const templates = useWhatsAppTemplates(canRead && hasPermission(PERMISSIONS.WHATSAPP.SEND) && !windowOpen);
  const canAssign = hasPermission(PERMISSIONS.WHATSAPP.ASSIGN);
  const canResolveIdentity = hasPermission(PERMISSIONS.INTEGRATIONS.MANAGE);
  const assignees = useWhatsAppAssignees(canAssign && !!selected);
  const markedRead = useRef('');
  const [textDrafts, setTextDrafts] = useState<Record<string, string>>({});
  const [pendingTextRequests, setPendingTextRequests] = useState<Record<string, { body: string; key: string }>>({});
  const [pendingTemplateRequests, setPendingTemplateRequests] = useState<Record<string, { fingerprint: string; key: string }>>({});
  const form = useForm<{ body: string }>({ resolver: zodResolver(whatsappMessageFormSchema), defaultValues: { body: '' } });
  const templateDraft = templateDrafts[requestScope] ?? { templateId: '', parameters: '' };
  const templateId = templateDraft.templateId;
  const templateParameters = templateDraft.parameters;
  const draftBody = textDrafts[requestScope] ?? '';

  useEffect(() => {
    form.setValue('body', draftBody);
  }, [draftBody, form, requestScope]);

  useEffect(() => {
    const initial = window.setTimeout(() => setCurrentTime(Date.now()), 0);
    const timer = window.setInterval(() => setCurrentTime(Date.now()), 60_000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(params);
      if (search) next.set('search', search); else next.delete('search');
      router.replace(`/whatsapp${next.size ? `?${next}` : ''}`);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [params, router, search]);

  useEffect(() => {
    if (!selected || messageOffset !== 0 || !messages.data) return;
    const newestInbound = [...messages.data]
      .reverse()
      .find((message) => message.direction === 'INBOUND');
    const readKey = newestInbound ? `${selected}:${newestInbound.id}` : '';
    if (newestInbound && markedRead.current !== readKey) {
      markedRead.current = readKey;
      void action.mutateAsync({ type: 'read', message_id: newestInbound.id }).catch(() => {
        markedRead.current = '';
      });
    }
  }, [action, messageOffset, messages.data, selected]);

  const open = (conversation: WhatsAppConversationDto) => {
    setMessageOffset(0);
    const next = new URLSearchParams(params);
    next.set('conversation', conversation.id);
    router.replace(`/whatsapp?${next}`);
  };
  const submit = async ({ body }: { body: string }) => {
    const requestFingerprint = JSON.stringify([requestScope, body]);
    const pendingRequest = pendingTextRequests[requestFingerprint];
    const request = pendingRequest?.body === body
      ? pendingRequest
      : { body, key: crypto.randomUUID().replaceAll('-', '') };
    setPendingTextRequests((current) => ({ ...current, [requestFingerprint]: request }));
    try {
      await send.mutateAsync({ body, idempotency_key: request.key });
      setPendingTextRequests((current) => {
        if (current[requestFingerprint]?.key !== request.key) return current;
        const next = { ...current };
        delete next[requestFingerprint];
        return next;
      });
      setTextDrafts((current) => current[requestScope] === body
        ? { ...current, [requestScope]: '' }
        : current);
    } catch (error) { toast.error(getErrorMessage(error, 'Message could not be queued.')); }
  };
  const submitTemplate = async () => {
    const template = templates.data?.find((item) => item.id === templateId);
    const values = templateParameters.split('\n').map((value) => value.trim()).filter(Boolean);
    if (!template || values.length !== template.body_parameter_count) {
      toast.error(`This template requires ${template?.body_parameter_count ?? 0} parameter values, one per line.`);
      return;
    }
    const fingerprint = JSON.stringify([template.id, values]);
    const submittedDraft = { templateId, parameters: templateParameters };
    const requestFingerprint = JSON.stringify([requestScope, fingerprint]);
    const pendingRequest = pendingTemplateRequests[requestFingerprint];
    const request = pendingRequest?.fingerprint === fingerprint
      ? pendingRequest
      : { fingerprint, key: crypto.randomUUID().replaceAll('-', '') };
    setPendingTemplateRequests((current) => ({ ...current, [requestFingerprint]: request }));
    try {
      await sendTemplate.mutateAsync({ template_id: template.id, parameters: values, idempotency_key: request.key });
      setPendingTemplateRequests((current) => {
        if (current[requestFingerprint]?.key !== request.key) return current;
        const next = { ...current };
        delete next[requestFingerprint];
        return next;
      });
      setTemplateDrafts((current) => {
        const currentDraft = current[requestScope];
        if (
          currentDraft?.templateId !== submittedDraft.templateId
          || currentDraft.parameters !== submittedDraft.parameters
        ) return current;
        return {
          ...current,
          [requestScope]: { ...currentDraft, parameters: '' },
        };
      });
    } catch (error) { toast.error(getErrorMessage(error, 'Template could not be queued.')); }
  };

  if (!canRead) return <Card className="p-6 text-sm">You do not have access to WhatsApp conversations.</Card>;
  return <div className="grid min-h-[65vh] grid-cols-1 gap-4 lg:grid-cols-[22rem_1fr]">
    <Card className="overflow-hidden">
      <div className="border-b p-4"><Input aria-label="Search conversations" placeholder="Search customer phone" value={search} onChange={(event) => { setSearch(event.target.value); setConversationOffset(0); }} /></div>
      {list.isLoading ? <Loader2 className="m-6 size-5 animate-spin" aria-label="Loading conversations" /> : list.isError ? <p className="p-4 text-sm text-destructive" role="alert">{getErrorMessage(list.error, 'Unable to load conversations.')}</p> : !list.data?.length ? <p className="p-4 text-sm text-muted-foreground">No conversations found.</p> : <ul>{list.data.map((item) => <li key={item.id}><button type="button" onClick={() => open(item)} className="flex min-h-20 w-full items-center justify-between border-b p-4 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2"><span><span className="block font-medium">{item.customer_phone}</span><span className="text-xs text-muted-foreground">{item.identity_state.replaceAll('_', ' ')} · {item.ai_enabled ? 'AI' : 'Human'}</span></span>{item.unread_count > 0 && <span className="rounded-full bg-primary px-2 py-1 text-xs text-primary-foreground">{item.unread_count}</span>}</button></li>)}</ul>}
      {!list.isLoading && !list.isError && (conversationOffset > 0 || (list.data?.length ?? 0) === 50) && <div className="flex justify-between border-t p-3"><Button type="button" size="sm" variant="outline" disabled={conversationOffset === 0} onClick={() => setConversationOffset((value) => Math.max(0, value - 50))}>Previous</Button><Button type="button" size="sm" variant="outline" disabled={(list.data?.length ?? 0) < 50} onClick={() => setConversationOffset((value) => value + 50)}>Next</Button></div>}
    </Card>
    <Card className="flex min-h-[65vh] flex-col overflow-hidden">
      {!selected ? <div className="m-auto text-center text-muted-foreground"><MessageCircle className="mx-auto mb-2 size-8" /><p>Select a conversation.</p></div> : detail.isError ? <p className="p-6 text-destructive" role="alert">{getErrorMessage(detail.error, 'Conversation is unavailable.')}</p> : <>
        <header className="flex flex-wrap items-center justify-between gap-2 border-b p-4"><div><h1 className="font-semibold">{detail.data?.customer_phone ?? 'Conversation'}</h1><p className="text-xs text-muted-foreground">{detail.data?.status} · {detail.data?.identity_state}</p></div><div className="flex flex-wrap gap-2">
          {detail.data?.contact_id && <Button asChild size="sm" variant="outline"><Link href={`/contacts/${detail.data.contact_id}`}>Contact</Link></Button>}{detail.data?.lead_id && <Button asChild size="sm" variant="outline"><Link href={`/leads/${detail.data.lead_id}`}>Lead</Link></Button>}
          {canAssign && <select aria-label="Assigned agent" className="h-9 rounded-md border bg-background px-2 text-sm" disabled={action.isPending || assignees.isLoading} value={detail.data?.assigned_user_id ?? ''} onChange={(event) => void action.mutateAsync({ type: 'update', payload: { assigned_user_id: event.target.value || null } }).catch((error) => toast.error(getErrorMessage(error, 'Assignment could not be updated.')))}><option value="">Unassigned</option>{assignees.data?.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}</select>}
          {canResolveIdentity && detail.data && <select aria-label="Communication preference" className="h-9 rounded-md border bg-background px-2 text-sm" disabled={identityAction.isPending} value={detail.data.consent} onChange={(event) => void identityAction.mutateAsync({ type: 'consent', consent: event.target.value as 'UNKNOWN' | 'OPTED_IN' | 'OPTED_OUT' }).catch((error) => toast.error(getErrorMessage(error, 'Communication preference could not be updated.')))}><option value="UNKNOWN">Consent unknown</option><option value="OPTED_IN">Opted in</option><option value="OPTED_OUT">Opted out</option></select>}
          {hasPermission(PERMISSIONS.WHATSAPP.MANAGE_AI) && <Button type="button" size="sm" variant="outline" disabled={action.isPending || !detail.data?.identity_state.startsWith('MATCHED')} onClick={() => void action.mutateAsync({ type: 'update', payload: { ai_enabled: !detail.data?.ai_enabled } }).catch((error) => toast.error(getErrorMessage(error, 'AI status could not be updated.')))}>{detail.data?.ai_enabled ? 'Disable AI' : 'Enable AI'}</Button>}
          {hasPermission(PERMISSIONS.WHATSAPP.TAKEOVER) && detail.data?.status !== 'HUMAN_HANDOFF' && <Button type="button" size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutateAsync({ type: 'takeover' })}>Take over</Button>}
        </div></header>
        {canResolveIdentity && detail.data && !detail.data.identity_state.startsWith('MATCHED') && <div className="flex flex-wrap items-end gap-2 border-b bg-muted/30 p-3"><label className="text-xs">Resolve as<select aria-label="Identity type" className="mt-1 block h-9 rounded-md border bg-background px-2 text-sm" value={resolutionType} onChange={(event) => setResolutionType(event.target.value as 'contact' | 'lead')}><option value="contact">Contact</option><option value="lead">Lead</option></select></label><label className="min-w-56 flex-1 text-xs">CRM record ID<Input className="mt-1" aria-label="CRM record ID" value={resolutionId} onChange={(event) => setResolutionId(event.target.value)} /></label><Button type="button" size="sm" disabled={!resolutionId.trim() || identityAction.isPending} onClick={() => void identityAction.mutateAsync({ type: 'resolve', entity_type: resolutionType, entity_id: resolutionId.trim() }).then(() => setResolutionId('')).catch((error) => toast.error(getErrorMessage(error, 'Identity could not be verified.')))}>Verify matching phone</Button></div>}
        <div className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">{messages.isLoading ? <Loader2 className="size-5 animate-spin" aria-label="Loading messages" /> : messages.isError ? <p className="text-sm text-destructive">{getErrorMessage(messages.error, 'Unable to load messages.')}</p> : <>{!messages.data?.length ? <p className="text-sm text-muted-foreground">No messages yet.</p> : messages.data.map((message) => <article key={message.id} className={`max-w-[85%] rounded-xl border p-3 ${message.direction === 'OUTBOUND' ? 'ml-auto bg-primary/5' : ''}`}><div className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">{message.source === 'AI' ? <Bot className="size-3" /> : <UserRound className="size-3" />}{message.source} · {message.status}</div><p className="whitespace-pre-wrap break-words text-sm">{message.body ?? `[${message.message_type}]`}</p>{message.error_message && <p className="mt-2 text-xs text-destructive">{message.error_message}</p>}{hasPermission(PERMISSIONS.WHATSAPP.SEND) && message.retryable && <Button type="button" size="sm" variant="outline" className="mt-2" disabled={retryMessage.isPending} onClick={() => void retryMessage.mutateAsync(message.id).catch((error) => toast.error(getErrorMessage(error, 'Message retry could not be queued.')))}>Retry safely</Button>}{message.media_available && <a className="mt-2 inline-block text-sm underline" href={`${BASE_URL}/whatsapp/conversations/${encodeURIComponent(selected)}/messages/${encodeURIComponent(message.id)}/media`}>Download media</a>}</article>)}{(messageOffset > 0 || (messages.data?.length ?? 0) === 100) && <div className="flex justify-center gap-2"><Button type="button" size="sm" variant="outline" disabled={(messages.data?.length ?? 0) < 100} onClick={() => setMessageOffset((value) => value + 100)}>Older</Button><Button type="button" size="sm" variant="outline" disabled={messageOffset === 0} onClick={() => setMessageOffset((value) => Math.max(0, value - 100))}>Newer</Button></div>}</>}</div>
        {detail.data?.consent === 'OPTED_OUT' ? <p className="border-t p-4 text-sm text-destructive">This customer opted out. Outbound WhatsApp messaging is disabled.</p> : hasPermission(PERMISSIONS.WHATSAPP.SEND) && (windowOpen ? <Form {...form}><form onSubmit={form.handleSubmit(submit)} className="flex items-end gap-2 border-t p-4"><FormField control={form.control} name="body" render={({ field }) => <FormItem className="flex-1"><FormControl><Textarea {...field} value={draftBody} aria-label="WhatsApp message" rows={2} placeholder="Type a message" onChange={(event) => { field.onChange(event); setTextDrafts((current) => ({ ...current, [requestScope]: event.target.value })); }} /></FormControl><FormMessage /></FormItem>} /><Button type="submit" size="icon" aria-label="Send message" disabled={send.isPending}><Send className="size-4" /></Button></form></Form> : <div className="space-y-2 border-t p-4"><p className="text-xs text-muted-foreground">The service window is closed. Select an approved template.</p><select aria-label="Approved template" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={templateId} onChange={(event) => setTemplateDrafts((current) => ({ ...current, [requestScope]: { ...templateDraft, templateId: event.target.value } }))}><option value="">Select template</option>{templates.data?.filter((item) => item.status === 'APPROVED').map((item) => <option key={item.id} value={item.id}>{item.name} ({item.language})</option>)}</select><Textarea aria-label="Template parameters" value={templateParameters} onChange={(event) => setTemplateDrafts((current) => ({ ...current, [requestScope]: { ...templateDraft, parameters: event.target.value } }))} placeholder="One parameter value per line" /><Button type="button" disabled={!templateId || sendTemplate.isPending} onClick={submitTemplate}>Send approved template</Button></div>)}
      </>}
    </Card>
  </div>;
}
