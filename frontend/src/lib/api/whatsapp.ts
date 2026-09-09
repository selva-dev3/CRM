'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { getOrganizationContext } from '@/lib/organization-context';
import { useAuth } from '@/providers/auth-provider';
import { whatsappAssigneeSchema, whatsappConversationSchema, whatsappIntegrationSchema, whatsappMessageSchema, whatsappTemplateSchema, type WhatsAppConfigForm } from '@/lib/types/whatsapp';

export const whatsappKeys = {
  all: (scope: string) => ['whatsapp', scope] as const,
  status: (scope: string) => [...whatsappKeys.all(scope), 'status'] as const,
  list: (scope: string, search: string, offset: number) => [...whatsappKeys.all(scope), 'conversations', search, offset] as const,
  detail: (scope: string, id: string) => [...whatsappKeys.all(scope), 'conversation', id] as const,
  messages: (scope: string, id: string, offset: number) => [...whatsappKeys.detail(scope, id), 'messages', offset] as const,
  templates: (scope: string) => [...whatsappKeys.all(scope), 'templates'] as const,
  assignees: (scope: string) => [...whatsappKeys.all(scope), 'assignees'] as const,
};

export function useWhatsAppScope() {
  const { user } = useAuth();
  return `${user?.id ?? ''}:${getOrganizationContext() ?? user?.organization_id ?? ''}`;
}

export function useWhatsAppStatus(enabled = true) {
  const scope = useWhatsAppScope();
  return useQuery({ queryKey: whatsappKeys.status(scope), enabled, queryFn: async ({ signal }) => whatsappIntegrationSchema.parse(await apiClient.get('/whatsapp/status', { signal })) });
}

export function useWhatsAppConversations(search: string, offset: number, enabled: boolean) {
  const scope = useWhatsAppScope();
  return useQuery({ queryKey: whatsappKeys.list(scope, search, offset), enabled,
    queryFn: async ({ signal }) => whatsappConversationSchema.array().parse(await apiClient.get(`/whatsapp/conversations?search=${encodeURIComponent(search)}&offset=${offset}&limit=50`, { signal })),
    refetchInterval: 15000, refetchIntervalInBackground: false });
}

export function useWhatsAppConversation(id: string, enabled: boolean) {
  const scope = useWhatsAppScope();
  return useQuery({ queryKey: whatsappKeys.detail(scope, id), enabled: enabled && !!id,
    queryFn: async ({ signal }) => whatsappConversationSchema.parse(await apiClient.get(`/whatsapp/conversations/${encodeURIComponent(id)}`, { signal })),
    refetchInterval: 5000, refetchIntervalInBackground: false });
}

export function useWhatsAppMessages(id: string, offset: number, enabled: boolean) {
  const scope = useWhatsAppScope();
  return useQuery({ queryKey: whatsappKeys.messages(scope, id, offset), enabled: enabled && !!id,
    queryFn: async ({ signal }) => whatsappMessageSchema.array().parse(await apiClient.get(`/whatsapp/conversations/${encodeURIComponent(id)}/messages?offset=${offset}&limit=100`, { signal })),
    refetchInterval: offset === 0 ? 5000 : false, refetchIntervalInBackground: false });
}

export function useWhatsAppTemplates(enabled: boolean) {
  const scope = useWhatsAppScope();
  return useQuery({ queryKey: whatsappKeys.templates(scope), enabled, queryFn: async ({ signal }) => whatsappTemplateSchema.array().parse(await apiClient.get('/whatsapp/templates', { signal })) });
}

export function useWhatsAppAssignees(enabled: boolean) {
  const scope = useWhatsAppScope();
  return useQuery({ queryKey: whatsappKeys.assignees(scope), enabled, queryFn: async ({ signal }) => whatsappAssigneeSchema.array().parse(await apiClient.get('/whatsapp/assignees', { signal })) });
}

export function useWhatsAppSend(id: string) {
  const scope = useWhatsAppScope();
  const client = useQueryClient();
  return useMutation({ retry: false, mutationFn: async (payload: { body: string; idempotency_key: string }) => whatsappMessageSchema.parse(await apiClient.post(`/whatsapp/conversations/${encodeURIComponent(id)}/messages`, payload)),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: whatsappKeys.all(scope) }); } });
}

export function useWhatsAppSendTemplate(id: string) {
  const scope = useWhatsAppScope();
  const client = useQueryClient();
  return useMutation({ retry: false, mutationFn: async (payload: { template_id: string; parameters: string[]; idempotency_key: string }) => whatsappMessageSchema.parse(await apiClient.post(`/whatsapp/conversations/${encodeURIComponent(id)}/template-messages`, payload)),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: whatsappKeys.all(scope) }); } });
}

export function useWhatsAppConversationAction(id: string) {
  const scope = useWhatsAppScope();
  const client = useQueryClient();
  return useMutation({ retry: false, mutationFn: async (action: { type: 'takeover' } | { type: 'read'; message_id: string } | { type: 'update'; payload: { ai_enabled?: boolean; status?: string; assigned_user_id?: string | null } }) => {
    const path = `/whatsapp/conversations/${encodeURIComponent(id)}`;
    return action.type === 'update'
      ? apiClient(path, { method: 'PATCH', body: JSON.stringify(action.payload) })
      : action.type === 'read'
        ? apiClient.post(`${path}/read`, { message_id: action.message_id })
        : apiClient.post(`${path}/takeover`);
  }, onSuccess: async () => { await client.invalidateQueries({ queryKey: whatsappKeys.all(scope) }); } });
}

export function useWhatsAppIdentityAction(conversationId: string, identityId: string) {
  const scope = useWhatsAppScope();
  const client = useQueryClient();
  return useMutation({ retry: false, mutationFn: async (action: { type: 'consent'; consent: 'UNKNOWN' | 'OPTED_IN' | 'OPTED_OUT' } | { type: 'resolve'; entity_type: 'contact' | 'lead'; entity_id: string }) => action.type === 'consent'
    ? apiClient(`/whatsapp/identities/${encodeURIComponent(identityId)}/consent`, { method: 'PATCH', body: JSON.stringify({ consent: action.consent }) })
    : apiClient.post(`/whatsapp/identities/${encodeURIComponent(identityId)}/resolve`, { entity_type: action.entity_type, entity_id: action.entity_id, ownership_verified: true }),
  onSuccess: async () => {
    await client.invalidateQueries({ queryKey: whatsappKeys.all(scope) });
  } });
}

export function useWhatsAppConfiguration() {
  const scope = useWhatsAppScope();
  const client = useQueryClient();
  // Credential submission deliberately stays out of mutation state/cache.
  const configure = async (values: WhatsAppConfigForm) => {
    const result = whatsappIntegrationSchema.parse(await apiClient.post('/whatsapp/integration', { ...values,
      default_phone_region: values.default_phone_region || null, ai_user_id: values.ai_user_id || null,
      default_assignee_id: values.default_assignee_id || null, enabled: false }));
    client.setQueryData(whatsappKeys.status(scope), result);
  };
  const action = useMutation({ retry: false, mutationFn: (operation: 'verify' | 'normalize-phones' | 'sync-templates' | 'disconnect') => operation === 'disconnect' ? apiClient.delete('/whatsapp/integration') : operation === 'sync-templates' ? apiClient.post('/whatsapp/templates/sync') : apiClient.post(`/whatsapp/integration/${operation}`),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: whatsappKeys.status(scope) }); } });
  return { configure, action };
}
